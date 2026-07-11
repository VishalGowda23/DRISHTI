"""
RiskLens AI — Claude Client (LangChain Integration)
Wraps the Anthropic Claude API via LangChain for structured analysis.
Includes retry logic, fallback, caching, and LangSmith tracing.
"""

import json
import time
from typing import Optional
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_core.output_parsers import JsonOutputParser

try:
    from langchain.callbacks.tracers import LangChainTracer
except ImportError:
    LangChainTracer = None  # optional — only used for LangSmith tracing

from app.core.config import get_settings
from app.core.logger import get_logger
from app.infrastructure.ai.prompt_templates import (
    build_concentration_analysis_prompt,
    get_system_prompt,
)
from app.domain.models.risk import ClaudeAnalysis, ModelInfo
from app.infrastructure.ai.langsmith_config import get_tracer
from app.infrastructure.ai.output_parsers import parse_claude_response

logger = get_logger("infrastructure.claude")


class ClaudeClient:
    """Claude API client with LangChain integration."""

    def __init__(self):
        settings = get_settings()
        self._model = ChatAnthropic(
            model=settings.claude_model,
            api_key=settings.anthropic_api_key,
            max_tokens=settings.claude_max_tokens,
            temperature=settings.claude_temperature,
        )
        self._max_retries = 3
        self._retry_delays = [1, 3, 5]
        # In-memory cache for cost and rate limit optimization: hash_key -> (ClaudeAnalysis, ModelInfo, timestamp)
        from cachetools import TTLCache
        self._cache = TTLCache(maxsize=1000, ttl=900)  # 15 minutes TTL, max 1000 items to prevent memory leaks

    async def analyze_portfolio_risk(
        self,
        portfolio_context: dict,
        rule_engine_results: dict,
        top_positions: list[dict],
        market_context: Optional[dict] = None,
    ) -> tuple[ClaudeAnalysis, ModelInfo]:
        """Send portfolio data to Claude for AI-powered risk analysis.

        Two-stage design:
        - Stage 1 (done before this call): Rule engine computed all numbers
        - Stage 2 (this call): Claude interprets, explains, and recommends

        Args:
            portfolio_context: Dict with portfolio_id, fund_name, fund_type, total_nav, etc.
            rule_engine_results: Pre-computed concentration checks from rule engine
            top_positions: Sorted and aggregated list of major positions
            market_context: Optional dict with volatility, price changes

        Returns:
            Tuple of (ClaudeAnalysis, ModelInfo)
        """
        # Generate cache key based on rule engine results and market context to save LLM tokens
        import hashlib
        
        payload_str = json.dumps(
            {"rules": rule_engine_results, "market": market_context or {}},
            sort_keys=True,
            default=str
        )
        cache_key = hashlib.sha256(payload_str.encode("utf-8")).hexdigest()

        # Check Cache Hit
        if cache_key in self._cache:
            cached_analysis, cached_model_info = self._cache[cache_key]
            logger.info(
                "LLM cache hit! Returning cached risk analysis.",
                portfolio_id=portfolio_context.get("portfolio_id")
            )
            return cached_analysis, cached_model_info

        from app.core.config import get_settings
        settings = get_settings()
        api_key = settings.anthropic_api_key
        if not api_key or len(api_key) < 20:
            logger.error("Missing or invalid ANTHROPIC_API_KEY. Failing fast without retries.")
            return self._fallback_analysis(rule_engine_results), ModelInfo()

        system_prompt = get_system_prompt()
        user_prompt = build_concentration_analysis_prompt(
            portfolio_context=portfolio_context,
            rule_engine_results=rule_engine_results,
            market_context=market_context or {},
            top_positions=top_positions,
        )

        start_time = time.time()
        tracer = get_tracer(portfolio_context.get('portfolio_id'))
        callbacks = [tracer] if tracer else []

        for attempt in range(self._max_retries):
            try:
                messages = [
                    SystemMessage(content=system_prompt),
                    HumanMessage(content=user_prompt),
                ]

                response = await self._model.ainvoke(messages, config={"callbacks": callbacks})
                elapsed_ms = int((time.time() - start_time) * 1000)

                # Parse JSON from response
                response_text = response.content
                analysis = parse_claude_response(response_text)

                # Token usage info
                model_info = ModelInfo(
                    model=get_settings().claude_model,
                    prompt_tokens=response.usage_metadata.get("input_tokens", 0) if response.usage_metadata else 0,
                    completion_tokens=response.usage_metadata.get("output_tokens", 0) if response.usage_metadata else 0,
                    total_cost_usd=0.0,  # Calculated based on token counts
                    langsmith_trace_id="",
                )

                logger.info(
                    "Claude analysis completed",
                    severity=analysis.severity,
                    confidence=analysis.confidence,
                    elapsed_ms=elapsed_ms,
                    prompt_tokens=model_info.prompt_tokens,
                    completion_tokens=model_info.completion_tokens,
                )

                # Cache the results
                self._cache[cache_key] = (analysis, model_info)
                return analysis, model_info

            except ValueError as e:
                logger.warning(
                    "Failed to parse Claude response",
                    attempt=attempt + 1,
                    error=str(e),
                )
                if attempt < self._max_retries - 1:
                    await self._wait(attempt)
                    continue
                return self._fallback_analysis(rule_engine_results), ModelInfo()

            except Exception as e:
                logger.error(
                    "Claude API call failed",
                    attempt=attempt + 1,
                    error=str(e),
                )
                if attempt < self._max_retries - 1:
                    await self._wait(attempt)
                    continue
                return self._fallback_analysis(rule_engine_results), ModelInfo()

        return self._fallback_analysis(rule_engine_results), ModelInfo()

    async def _wait(self, attempt: int) -> None:
        """Wait before retrying."""
        import asyncio
        delay = self._retry_delays[min(attempt, len(self._retry_delays) - 1)]
        logger.info(f"Retrying in {delay}s", attempt=attempt + 1)
        await asyncio.sleep(delay)

    def _fallback_analysis(self, rule_engine_results: dict) -> ClaudeAnalysis:
        """Fallback analysis when Claude is unavailable.

        Uses rule engine results directly without AI interpretation.
        """
        total_breaches = rule_engine_results.get("total_breaches", 0)
        total_warnings = rule_engine_results.get("total_warnings", 0)

        if total_breaches >= 2:
            severity = "CRITICAL"
        elif total_breaches >= 1:
            severity = "HIGH"
        elif total_warnings >= 1:
            severity = "MEDIUM"
        else:
            severity = "LOW"

        return ClaudeAnalysis(
            severity=severity,
            confidence=0.5,
            rationale=f"[AI UNAVAILABLE — Rule-based assessment] Found {total_breaches} breaches and {total_warnings} warnings.",
            breach_analysis=[],
            volatility_context="AI analysis unavailable — volatility context not assessed",
            historical_pattern="AI analysis unavailable",
            recommended_actions=["Manual review recommended — AI service temporarily unavailable"],
            estimated_review_time_minutes=30,
            overall_verdict=f"{severity} RISK — Rule-based assessment (AI unavailable)",
        )


# Singleton instance
_claude_client: Optional[ClaudeClient] = None


def get_claude_client() -> ClaudeClient:
    """Get or create the Claude client singleton."""
    global _claude_client
    if _claude_client is None:
        _claude_client = ClaudeClient()
    return _claude_client


# ============================================================================
# Direct-SDK Claude client — Kafka hot-path (kafka_risk_service.py)
#
# Uses the `anthropic` package directly (not LangChain) for:
#   - Tool-use / structured output via emit_risk_assessment tool
#   - Prompt caching on the static SYSTEM_PROMPT
#   - 3-tier fallback: Sonnet → Haiku → rule-engine-only
#
# Covers FR-11 (identify/explain breaches), FR-12 (severity verdict),
# FR-13 (confidence score), FR-14 (human-readable rationale).
#
# Critical design rule (Phase 2, Step 10.1): the rule engine did the math.
# This code NEVER asks Claude to compute a percentage, compare a number to
# a limit, or do arithmetic of any kind. It receives an already-filtered
# facts object (only BREACH/WARNING/FLAGGED rows) and asks for judgment.
# ============================================================================

import time as _time
from dataclasses import dataclass as _dataclass

try:
    import anthropic as _anthropic
    _ANTHROPIC_AVAILABLE = True
except ImportError:
    _ANTHROPIC_AVAILABLE = False
    logger.warning(
        "anthropic package not installed — Kafka-path Claude calls will use rule-engine fallback. "
        "Run: pip install anthropic"
    )

_PRIMARY_MODEL = "claude-sonnet-4-20250514"
_FALLBACK_MODEL = "claude-haiku-4-5-20251001"
_MAX_RETRIES = 3
_RETRY_DELAYS_SEC = [1, 3, 5]

# Kept short and STATIC on purpose — this is what gets prompt-cached.
# Any per-portfolio detail belongs in the user turn, never here, or
# the cache never hits.
_SYSTEM_PROMPT = (
    "You are a senior portfolio risk analyst at a top-tier asset management firm. "
    "You receive PRE-COMPUTED concentration, correlation, and volatility facts about a portfolio "
    "— never raw positions — and produce a structured risk assessment for a portfolio manager and risk desk.\n\n"
    "Rules:\n"
    "1. Never recompute or restate percentages beyond what is given to you.\n"
    "2. Assess severity considering how multiple flagged signals interact, not each one in isolation.\n"
    "3. Confidence should be LOWER when signals conflict or are marginal, HIGHER when the picture is unambiguous.\n"
    "4. Rationale must be 2-3 sentences, written for a PM who has 15 seconds to read it.\n"
    "5. Recommended actions must be specific (name the entity, the direction, and roughly how much) — never generic advice.\n"
    "6. Output ONLY valid JSON matching the provided schema. No prose outside the JSON."
)

_OUTPUT_TOOL = {
    "name": "emit_risk_assessment",
    "description": "Return the structured portfolio risk assessment.",
    "input_schema": {
        "type": "object",
        "properties": {
            "severity": {"type": "string", "enum": ["LOW", "MEDIUM", "HIGH", "CRITICAL"]},
            "confidence": {"type": "number", "minimum": 0.0, "maximum": 1.0},
            "rationale": {"type": "string"},
            "breach_analysis": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "type": {"type": "string"},
                        "entity": {"type": "string"},
                        "assessment": {"type": "string"},
                        "risk_level": {"type": "string", "enum": ["LOW", "MEDIUM", "HIGH", "CRITICAL"]},
                    },
                    "required": ["type", "entity", "assessment", "risk_level"],
                },
            },
            "volatility_context": {"type": "string"},
            "historical_pattern": {"type": "string"},
            "recommended_actions": {"type": "array", "items": {"type": "string"}},
            "estimated_review_time_minutes": {"type": "integer"},
            "overall_verdict": {"type": "string"},
        },
        "required": [
            "severity", "confidence", "rationale", "breach_analysis",
            "volatility_context", "historical_pattern",
            "recommended_actions", "estimated_review_time_minutes",
            "overall_verdict",
        ],
    },
}


@_dataclass
class ClaudeAnalysisResult:
    """Result from the direct-SDK Claude call (Kafka hot-path).
    Distinct from ClaudeAnalysis (Pydantic model used by REST path).
    """
    claude_analysis: dict
    model_info: dict
    ai_unavailable: bool = False


def _build_user_turn(portfolio_context: dict, facts: dict) -> str:
    """facts is ALREADY filtered to non-OK rows by kafka_risk_service —
    this function does not do that filtering itself, to keep the 'facts
    vs judgment' boundary in one place."""
    import json as _json
    return (
        f"### Portfolio Context\n{_json.dumps(portfolio_context, indent=2)}\n\n"
        f"### Flagged Concentration / Correlation / Volatility Facts\n"
        f"{_json.dumps(facts, indent=2)}\n\n"
        "Analyze the above and call emit_risk_assessment with your assessment."
    )


def _call_sdk_model(client, model: str, portfolio_context: dict, facts: dict) -> dict:
    response = client.messages.create(
        model=model,
        max_tokens=1024,
        system=[
            {
                "type": "text",
                "text": _SYSTEM_PROMPT,
                "cache_control": {"type": "ephemeral"},  # system prompt repeats every call
            }
        ],
        tools=[_OUTPUT_TOOL],
        tool_choice={"type": "tool", "name": "emit_risk_assessment"},
        messages=[{"role": "user", "content": _build_user_turn(portfolio_context, facts)}],
    )
    tool_use_block = next(b for b in response.content if b.type == "tool_use")
    return {
        "output": tool_use_block.input,
        "usage": {
            "prompt_tokens": response.usage.input_tokens,
            "completion_tokens": response.usage.output_tokens,
            "cache_read_tokens": getattr(response.usage, "cache_read_input_tokens", 0),
        },
    }


def _rule_engine_only_fallback(facts: dict) -> dict:
    """Last resort — no AI rationale, but the system still produces a
    usable, honest verdict instead of failing the demo outright."""
    has_breach = any(
        row.get("status") == "BREACH"
        for rows in facts.values()
        for row in (rows if isinstance(rows, list) else [])
    )
    severity = "HIGH" if has_breach else "MEDIUM"
    return {
        "severity": severity,
        "confidence": 0.4,
        "rationale": "AI analysis unavailable; severity derived from rule engine breach flags only.",
        "breach_analysis": [],
        "volatility_context": "unavailable",
        "historical_pattern": "unavailable",
        "recommended_actions": ["Manual review required — AI rationale unavailable."],
        "estimated_review_time_minutes": 30,
        "overall_verdict": f"{severity} RISK (rule-engine only, AI unavailable)",
    }


def call_claude_for_analysis(
    client,
    portfolio_context: dict,
    facts: dict,
) -> "ClaudeAnalysisResult":
    """FR-11/12/13/14 entry point for the Kafka hot-path.

    Implements the fallback hierarchy:
      1. Sonnet, with retries + exponential backoff
      2. Haiku (cheaper/faster) if Sonnet exhausts retries
      3. Rule-engine-only assessment, marked ai_unavailable, if both fail

    Never raises out to the caller — a demo cannot go down because
    Claude had one bad response.

    Args:
        client: An ``anthropic.Anthropic`` instance. If None or anthropic
                is not installed, falls back to rule-engine-only immediately.
        portfolio_context: Dict with fund metadata (portfolio_id, fund_name, nav, etc.)
        facts: Pre-filtered facts dict from ``build_claude_facts()`` — only
               BREACH/WARNING/FLAGGED rows, never all-OK rows.

    Returns:
        ClaudeAnalysisResult with claude_analysis dict and model_info.
    """
    if not _ANTHROPIC_AVAILABLE or client is None:
        return ClaudeAnalysisResult(
            claude_analysis=_rule_engine_only_fallback(facts),
            model_info={"model": "none", "fallback_reason": "anthropic package unavailable or client is None"},
            ai_unavailable=True,
        )

    last_error: Optional[Exception] = None

    for attempt in range(_MAX_RETRIES):
        try:
            start = _time.time()
            result = _call_sdk_model(client, _PRIMARY_MODEL, portfolio_context, facts)
            elapsed_ms = int((_time.time() - start) * 1000)
            return ClaudeAnalysisResult(
                claude_analysis=result["output"],
                model_info={
                    "model": _PRIMARY_MODEL,
                    **result["usage"],
                    "processing_time_ms": elapsed_ms,
                    "attempt": attempt + 1,
                },
            )
        except Exception as e:  # noqa: BLE001 — deliberately broad, this is a fallback boundary
            last_error = e
            if attempt < len(_RETRY_DELAYS_SEC):
                _time.sleep(_RETRY_DELAYS_SEC[attempt])

    try:
        result = _call_sdk_model(client, _FALLBACK_MODEL, portfolio_context, facts)
        return ClaudeAnalysisResult(
            claude_analysis=result["output"],
            model_info={"model": _FALLBACK_MODEL, **result["usage"], "fallback_reason": str(last_error)},
        )
    except Exception as e:  # noqa: BLE001
        return ClaudeAnalysisResult(
            claude_analysis=_rule_engine_only_fallback(facts),
            model_info={"model": "none", "fallback_reason": str(e)},
            ai_unavailable=True,
        )

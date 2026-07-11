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

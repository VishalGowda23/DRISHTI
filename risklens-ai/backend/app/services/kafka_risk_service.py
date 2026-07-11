"""
services/kafka_risk_service.py

Kafka-native risk analysis service. Wires domain/rules (pure math) to
infrastructure/ai (Claude judgment) via three event-handler functions
that map directly onto the Kafka pipeline:

  on_portfolio_created  <- portfolio.created / portfolio.events
  on_price_tick         <- market.prices.realtime
  on_position_changed   <- portfolio.positions.changed (trade simulator / shock API)

This is deliberately separate from the existing RiskAnalysisService
(which handles REST-triggered, manual analysis). Both coexist — this
module is the real-time hot path; RiskAnalysisService is the
on-demand cold path.

Also implements the two remaining Phase 2 Step 10.4 token-optimization
levers that don't belong in claude_client.py itself:
  - "send only breaches/warnings" (build_claude_facts)
  - "cache identical portfolios" (facts_hash + AssessmentCache)
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass, field
from typing import Optional

from app.core.logger import get_logger
from app.domain.rules.concentration_rules_v2 import (
    ConcentrationLimits,
    PortfolioConcentrationState,
    apply_position_delta,
    build_rule_engine_results,
    full_recompute,
)
from app.domain.rules.correlation_rules_v2 import CorrelationCache, ReturnSeriesStore
from app.infrastructure.ai.claude_client import ClaudeAnalysisResult, call_claude_for_analysis

logger = get_logger("services.kafka_risk")


# ---------------------------------------------------------------------
# Trigger + facts construction (token optimization)
# ---------------------------------------------------------------------

def _only_flagged(rows: list[dict]) -> list[dict]:
    return [r for r in rows if r.get("status") in ("BREACH", "WARNING", "FLAGGED")]


def should_trigger_claude(rule_engine_results: dict, correlation_clusters: list[dict]) -> bool:
    """FR-11 gate. A clean scan costs zero Claude tokens — this is the
    single biggest lever in the token-optimization strategy, bigger
    than prompt shrinking."""
    for key in ("issuer_checks", "sector_checks", "geography_checks", "asset_class_checks"):
        if _only_flagged(rule_engine_results.get(key, [])):
            return True
    if rule_engine_results.get("diversification_flags"):
        return True
    if correlation_clusters:
        return True
    return False


def build_claude_facts(
    rule_engine_results: dict,
    correlation_clusters: list[dict],
    volatility_snapshots: list[dict],
    historical_context: Optional[list[dict]] = None,
) -> dict:
    """Phase 2 Step 10.4: 'send only breaches/warnings'. OK-status rows
    are dropped entirely — they cost tokens and add nothing Claude
    needs to reason about severity."""
    facts = {
        "issuer_flags": _only_flagged(rule_engine_results.get("issuer_checks", [])),
        "sector_flags": _only_flagged(rule_engine_results.get("sector_checks", [])),
        "geography_flags": _only_flagged(rule_engine_results.get("geography_checks", [])),
        "asset_class_flags": _only_flagged(rule_engine_results.get("asset_class_checks", [])),
        "diversification_flags": rule_engine_results.get("diversification_flags", []),
        "correlation_clusters": correlation_clusters,
        "volatility_signals": [
            v for v in volatility_snapshots
            if v.get("qoq_change_pct") is not None and abs(v["qoq_change_pct"]) >= 15
        ],
    }
    if historical_context:
        facts["historical_context"] = historical_context
    return facts


def facts_hash(facts: dict) -> str:
    """Coarse rounding before hashing so near-identical ticks (e.g.
    9.81% vs 9.83% NAV from a price wobble) still dedupe, instead of
    every micro-change forcing a fresh Claude call."""
    def _round_floats(obj):
        if isinstance(obj, float):
            return round(obj, 1)
        if isinstance(obj, dict):
            return {k: _round_floats(v) for k, v in sorted(obj.items())}
        if isinstance(obj, list):
            return [_round_floats(v) for v in obj]
        return obj

    normalized = json.dumps(_round_floats(facts), sort_keys=True)
    return hashlib.sha256(normalized.encode()).hexdigest()


@dataclass
class AssessmentCache:
    """FR-11 / Step 10.4 'cache identical portfolios' — 100% token
    savings when the same facts recur (very common: a portfolio can
    sit in the same breach state across many ticks before anyone
    rebalances)."""

    _store: dict[str, tuple[float, ClaudeAnalysisResult]] = field(default_factory=dict)
    ttl_sec: float = 900.0  # re-verify with a fresh Claude call at least every 15 min

    def get(self, key: str) -> Optional[ClaudeAnalysisResult]:
        entry = self._store.get(key)
        if entry is None:
            return None
        cached_at, result = entry
        if time.time() - cached_at > self.ttl_sec:
            return None
        return result

    def put(self, key: str, result: ClaudeAnalysisResult) -> None:
        self._store[key] = (time.time(), result)


# ---------------------------------------------------------------------
# Per-process runtime registries (swap for Redis when scaling out)
# ---------------------------------------------------------------------

_concentration_states: dict[str, PortfolioConcentrationState] = {}
_return_series_store = ReturnSeriesStore()
_correlation_caches: dict[str, CorrelationCache] = {}
_assessment_cache = AssessmentCache()

RECONCILE_EVERY_N_TICKS = 250


# ---------------------------------------------------------------------
# Kafka event handlers — called from existing worker code
# (portfolio.events / market.prices.realtime topics)
# ---------------------------------------------------------------------

def on_portfolio_created(positions: list[dict], limits_doc: dict) -> None:
    """Handle `portfolio.created`. positions = full list from the
    `positions` Mongo collection for this portfolio_id.

    Call this when a new portfolio is seeded into Mongo.
    limits_doc must have a 'limits' sub-dict with keys matching
    ConcentrationLimits.from_mongo_doc(). If limits_doc is None or
    missing required keys, falls back to DEFAULT_RISK_LIMITS.
    """
    try:
        limits = ConcentrationLimits.from_mongo_doc(limits_doc)
    except (KeyError, TypeError):
        logger.warning(
            "on_portfolio_created: limits_doc missing or malformed, using defaults",
            limits_doc=str(limits_doc)[:200],
        )
        limits = ConcentrationLimits.from_defaults()

    try:
        state, _ = full_recompute(positions, limits)
        _concentration_states[state.portfolio_id] = state
        _correlation_caches[state.portfolio_id] = CorrelationCache()
        logger.info(
            "Portfolio state initialised",
            portfolio_id=state.portfolio_id,
            nav=state.nav,
            holdings=state.holdings_count,
        )
    except Exception as exc:
        logger.error("on_portfolio_created failed", error=str(exc))


def on_price_tick(symbol: str, price: float, quarter_boundary: bool = False) -> None:
    """Handle `market.prices.realtime`. O(1).

    Feed every price tick here to keep the Welford volatility
    accumulators and the 30-day return window up-to-date. This must
    be called BEFORE correlation_cache.maybe_refresh() on the same
    tick for the freshest data.
    """
    _return_series_store.on_price_tick(symbol, price, quarter_boundary)


def on_position_changed(
    portfolio_id: str,
    *,
    issuer: str,
    sector: str,
    country: str,
    asset_class: str,
    is_cash: bool,
    old_market_value: float,
    new_market_value: float,
    limits_doc: Optional[dict],
    sectors_map: dict[str, list[str]],
    claude_client,
    portfolio_context: dict,
) -> Optional[dict]:
    """Handle `portfolio.positions.changed`. This is the hot path.

    Returns an assessment dict ready to persist to `assessments` and
    feed to the alert/notification service — or None if nothing
    warranted a full assessment this tick (still O(1) either way).

    on_position_changed returns None on most calls — that's
    intentional, not a bug. It only returns a full assessment dict
    when a tick actually crossed a threshold AND should_trigger_claude
    decided there's something worth Claude's judgment. When it returns
    a dict, write it to Mongo as-is, then hand portfolio_id +
    claude_analysis.severity to the notification service.
    """
    state = _concentration_states.get(portfolio_id)
    if state is None:
        logger.warning(
            "on_position_changed: no state for portfolio — "
            "call on_portfolio_created first; skipping this tick",
            portfolio_id=portfolio_id,
        )
        return None

    try:
        if limits_doc:
            limits = ConcentrationLimits.from_mongo_doc(limits_doc)
        else:
            limits = ConcentrationLimits.from_defaults()
    except (KeyError, TypeError):
        limits = ConcentrationLimits.from_defaults()

    tick_flags = apply_position_delta(
        state,
        issuer=issuer, sector=sector, country=country, asset_class=asset_class,
        is_cash=is_cash, old_market_value=old_market_value, new_market_value=new_market_value,
        limits=limits,
    )

    # Periodic reconciliation guard — log, but let the caller trigger
    # a full_recompute from Mongo on its own schedule.
    if state.ticks_since_reconcile >= RECONCILE_EVERY_N_TICKS:
        logger.info(
            "Reconciliation due — caller should trigger full_recompute from Mongo",
            portfolio_id=portfolio_id,
            ticks=state.ticks_since_reconcile,
        )

    if not tick_flags:
        return None  # nothing crossed a threshold — zero downstream cost, by design

    rule_engine_results = build_rule_engine_results(state, limits)
    correlation_cache = _correlation_caches.setdefault(portfolio_id, CorrelationCache())
    clusters = correlation_cache.maybe_refresh(sectors_map, _return_series_store, limits.correlation_threshold)

    if not should_trigger_claude(rule_engine_results, clusters):
        return None

    volatility_snapshots = [
        snap for snap in (
            _return_series_store.volatility_snapshot(sym)
            for sector_syms in sectors_map.values()
            for sym in sector_syms
        ) if snap is not None
    ]

    facts = build_claude_facts(rule_engine_results, clusters, volatility_snapshots)
    cache_key = facts_hash(facts)

    cached = _assessment_cache.get(cache_key)
    claude_result = cached if cached is not None else call_claude_for_analysis(
        claude_client, portfolio_context, facts
    )
    if cached is None:
        _assessment_cache.put(cache_key, claude_result)

    logger.info(
        "Assessment produced",
        portfolio_id=portfolio_id,
        severity=claude_result.claude_analysis.get("severity", "?"),
        cache_hit=cached is not None,
        ai_unavailable=claude_result.ai_unavailable,
    )

    return {
        "portfolio_id": portfolio_id,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "trigger": "kafka_event",
        "status": "ai_unavailable" if claude_result.ai_unavailable else "completed",
        "nav_at_assessment": state.nav,
        "rule_engine_results": {**rule_engine_results, "correlation_clusters": clusters},
        "claude_analysis": claude_result.claude_analysis,
        "model_info": claude_result.model_info,
        "facts_cache_hit": cached is not None,
    }


# ---------------------------------------------------------------------
# Scaling note:
#
# _concentration_states / _correlation_caches / _assessment_cache are
# plain in-process dicts, which is correct for a single demo process.
# To scale beyond one process:
#   - PortfolioConcentrationState -> Redis hash, keyed by portfolio_id
#   - CorrelationCache            -> Redis, TTL = refresh_interval_sec
#   - AssessmentCache             -> Redis, TTL already modeled above
# None of the function signatures above need to change for that swap —
# only what backs the dict lookups does.
# ---------------------------------------------------------------------

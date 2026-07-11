"""
domain/rules/concentration_rules_v2.py

Covers FR-5 (evaluate against configurable limits), FR-6 (issuer),
FR-7 (sector), FR-8 (geography), FR-9 (asset class), FR-19 (per-fund
configurable limits).

Design rule (Phase 2, Step 10.1): this module does ONLY arithmetic and
comparisons. No Claude calls here, no natural-language anything. It
produces the exact `rule_engine_results` shape stored on the
`assessments` collection.

Two entry points, matching two real input shapes your Kafka pipeline
produces:

  - apply_position_delta(...)  -> hot path, O(1), called on every
    single position tick from the `portfolio.positions.changed` event.

  - full_recompute(...)        -> cold path, O(n) in number of
    positions, called on `portfolio.created` and periodically as a
    reconciliation pass to correct float drift from many deltas.

Both write into the same PortfolioConcentrationState, so the hot path
never has to re-derive anything the cold path already computed.

NOTE: This is the v2 stateful engine. The original concentration_rules.py
(stateless, used by RiskAnalysisService for REST-triggered analysis) is
preserved. This module is used by kafka_risk_service.py for the Kafka
hot-path.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class CheckStatus(str, Enum):
    OK = "OK"
    WARNING = "WARNING"
    BREACH = "BREACH"


@dataclass
class ConcentrationLimits:
    """Mirrors the `limits` sub-document on the risk_limits collection.
    Loaded once per portfolio (or per fund, with inheritance) — FR-19.
    """

    single_issuer_max: float
    sector_max: float
    geography_max: float
    asset_class_max: float
    correlation_threshold: float
    min_holdings: int
    max_cash_percentage: float
    warning_buffer_pct: float

    @classmethod
    def from_mongo_doc(cls, risk_limits_doc: dict) -> "ConcentrationLimits":
        limits = risk_limits_doc["limits"]
        return cls(
            single_issuer_max=limits["single_issuer_max"],
            sector_max=limits["sector_max"],
            geography_max=limits["geography_max"],
            asset_class_max=limits["asset_class_max"],
            correlation_threshold=limits["correlation_threshold"],
            min_holdings=limits["min_holdings"],
            max_cash_percentage=limits["max_cash_percentage"],
            warning_buffer_pct=risk_limits_doc.get("warning_buffer_pct", 3.0),
        )

    @classmethod
    def from_defaults(cls) -> "ConcentrationLimits":
        """Create limits from app constants (used when no per-portfolio config exists)."""
        from app.core.constants import DEFAULT_RISK_LIMITS, DEFAULT_WARNING_BUFFER_PCT
        d = DEFAULT_RISK_LIMITS
        return cls(
            single_issuer_max=d["single_issuer_max"],
            sector_max=d["sector_max"],
            geography_max=d["geography_max"],
            asset_class_max=d["asset_class_max"],
            correlation_threshold=d["correlation_threshold"],
            min_holdings=d["min_holdings"],
            max_cash_percentage=d["max_cash_percentage"],
            warning_buffer_pct=DEFAULT_WARNING_BUFFER_PCT,
        )


@dataclass
class PortfolioConcentrationState:
    """In-memory (or Redis-later) state for ONE portfolio_id.

    Rebuilt from Mongo on process start via full_recompute(); mutated
    in O(1) per tick thereafter via apply_position_delta().
    """

    portfolio_id: str
    nav: float = 0.0
    issuer_exposure: dict[str, float] = field(default_factory=dict)   # issuer -> market value
    sector_exposure: dict[str, float] = field(default_factory=dict)
    geo_exposure: dict[str, float] = field(default_factory=dict)
    asset_class_exposure: dict[str, float] = field(default_factory=dict)
    cash_exposure: float = 0.0
    holdings_count: int = 0
    ticks_since_reconcile: int = 0


def _classify(nav_pct: float, limit: float, warning_buffer_pct: float) -> CheckStatus:
    if nav_pct > limit:
        return CheckStatus.BREACH
    if nav_pct > limit - warning_buffer_pct:
        return CheckStatus.WARNING
    return CheckStatus.OK


def _check_dimension(
    dimension_key: str,
    exposure_map: dict[str, float],
    limit: float,
    nav: float,
    warning_buffer_pct: float,
) -> list[dict]:
    """Builds the issuer_checks / sector_checks / geography_checks /
    asset_class_checks list shape used in the `assessments` schema."""
    results = []
    for entity, value in exposure_map.items():
        if nav <= 0:
            continue
        nav_pct = round((value / nav) * 100, 4)
        status = _classify(nav_pct, limit, warning_buffer_pct)
        entry = {
            dimension_key: entity,
            "nav_pct": nav_pct,
            "limit": limit,
            "status": status.value,
        }
        if status == CheckStatus.BREACH:
            entry["excess_pct"] = round(nav_pct - limit, 4)
        elif status == CheckStatus.WARNING:
            entry["buffer_pct"] = round(limit - nav_pct, 4)
        results.append(entry)
    return results


# ---------------------------------------------------------------------
# HOT PATH — O(1) amortized. Called once per position tick.
# ---------------------------------------------------------------------

def apply_position_delta(
    state: PortfolioConcentrationState,
    *,
    issuer: str,
    sector: str,
    country: str,
    asset_class: str,
    is_cash: bool,
    old_market_value: float,
    new_market_value: float,
    limits: ConcentrationLimits,
) -> list[dict]:
    """FR-6/7/8/9 hot path. Touches only the 4 aggregates the changed
    position belongs to — never rescans the portfolio.

    Returns ONLY the check rows that materially changed (status != OK
    for the touched entities), so the caller can decide cheaply whether
    anything downstream needs to happen. Callers wanting the FULL
    current picture (e.g. to persist rule_engine_results) should call
    build_rule_engine_results() instead, which is also O(1)-ish since
    it iterates only populated buckets, not raw positions.
    """
    delta = new_market_value - old_market_value
    state.nav += delta

    state.issuer_exposure[issuer] = state.issuer_exposure.get(issuer, 0.0) + delta
    state.sector_exposure[sector] = state.sector_exposure.get(sector, 0.0) + delta
    state.geo_exposure[country] = state.geo_exposure.get(country, 0.0) + delta
    state.asset_class_exposure[asset_class] = (
        state.asset_class_exposure.get(asset_class, 0.0) + delta
    )
    if is_cash:
        state.cash_exposure += delta

    state.ticks_since_reconcile += 1

    flags: list[dict] = []
    checks = [
        ("issuer", issuer, state.issuer_exposure, limits.single_issuer_max),
        ("sector", sector, state.sector_exposure, limits.sector_max),
        ("country", country, state.geo_exposure, limits.geography_max),
        ("asset_class", asset_class, state.asset_class_exposure, limits.asset_class_max),
    ]
    for key_name, entity, exposure_map, limit in checks:
        if state.nav <= 0:
            continue
        nav_pct = round((exposure_map[entity] / state.nav) * 100, 4)
        status = _classify(nav_pct, limit, limits.warning_buffer_pct)
        if status != CheckStatus.OK:
            row = {key_name: entity, "nav_pct": nav_pct, "limit": limit, "status": status.value}
            row["excess_pct" if status == CheckStatus.BREACH else "buffer_pct"] = round(
                abs(nav_pct - limit), 4
            )
            flags.append(row)

    # cash ceiling — simple scalar check, cheap regardless
    if state.nav > 0:
        cash_pct = round((state.cash_exposure / state.nav) * 100, 4)
        if cash_pct > limits.max_cash_percentage:
            flags.append(
                {
                    "asset_class": "cash",
                    "nav_pct": cash_pct,
                    "limit": limits.max_cash_percentage,
                    "status": CheckStatus.BREACH.value,
                    "excess_pct": round(cash_pct - limits.max_cash_percentage, 4),
                }
            )

    return flags


# ---------------------------------------------------------------------
# COLD PATH — O(n) in number of positions. Reconciliation + full loads.
# ---------------------------------------------------------------------

def full_recompute(
    positions: list[dict],
    limits: ConcentrationLimits,
) -> tuple[PortfolioConcentrationState, dict]:
    """FR-5 baseline. Rebuilds state from scratch off the `positions`
    collection shape (symbol, sector, country, asset_class,
    market_value, nav_percentage, ...). Use on process start, and on a
    timer (e.g. every 200-500 ticks or every few minutes, whichever
    first) to correct float drift from many small hot-path deltas.
    """
    if not positions:
        raise ValueError("full_recompute called with zero positions")

    portfolio_id = positions[0]["portfolio_id"]
    state = PortfolioConcentrationState(portfolio_id=portfolio_id)

    for pos in positions:
        mv = pos["market_value"]
        state.nav += mv
        state.issuer_exposure[pos["name"]] = state.issuer_exposure.get(pos["name"], 0.0) + mv
        state.sector_exposure[pos["sector"]] = state.sector_exposure.get(pos["sector"], 0.0) + mv
        state.geo_exposure[pos["country"]] = state.geo_exposure.get(pos["country"], 0.0) + mv
        state.asset_class_exposure[pos["asset_class"]] = (
            state.asset_class_exposure.get(pos["asset_class"], 0.0) + mv
        )
        if pos["asset_class"] == "cash":
            state.cash_exposure += mv
        state.holdings_count += 1

    state.ticks_since_reconcile = 0
    results = build_rule_engine_results(state, limits)
    return state, results


def build_rule_engine_results(
    state: PortfolioConcentrationState,
    limits: ConcentrationLimits,
) -> dict:
    """Produces the exact `rule_engine_results` shape used on the
    `assessments` collection (issuer_checks / sector_checks /
    geography_checks / asset_class_checks). Correlation is stitched in
    separately by correlation_rules_v2.py — kept apart because it runs on
    a different refresh cadence.

    Cost: proportional to number of DISTINCT issuers/sectors/
    countries/asset-classes — not number of positions or ticks. For a
    typical multi-asset fund that's tens of buckets, not thousands.
    """
    min_holdings_breach = state.holdings_count < limits.min_holdings
    return {
        "issuer_checks": _check_dimension(
            "issuer", state.issuer_exposure, limits.single_issuer_max, state.nav, limits.warning_buffer_pct
        ),
        "sector_checks": _check_dimension(
            "sector", state.sector_exposure, limits.sector_max, state.nav, limits.warning_buffer_pct
        ),
        "geography_checks": _check_dimension(
            "country", state.geo_exposure, limits.geography_max, state.nav, limits.warning_buffer_pct
        ),
        "asset_class_checks": _check_dimension(
            "asset_class", state.asset_class_exposure, limits.asset_class_max, state.nav, limits.warning_buffer_pct
        ),
        "diversification_flags": (
            [{"type": "MIN_HOLDINGS_BREACH", "holdings_count": state.holdings_count, "min_required": limits.min_holdings}]
            if min_holdings_breach
            else []
        ),
    }

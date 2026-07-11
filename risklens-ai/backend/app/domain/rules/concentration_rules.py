"""
RiskLens AI — Concentration Rules Engine
Pure Python rule-based engine that pre-computes concentration checks.
No external dependencies. Fast. Exact. Free.
"""

from typing import List, Dict, Tuple
from collections import defaultdict
from app.domain.enums import BreachStatus, ConcentrationType
from app.domain.models.risk import ConcentrationCheck, RuleEngineResults, CorrelationCluster
from app.domain.models.audit import RiskLimits
from app.core.logger import get_logger

logger = get_logger("rules.concentration")


def _check_concentration(
    entity: str,
    nav_pct: float,
    limit: float,
    warning_buffer: float,
    concentration_type: ConcentrationType,
) -> ConcentrationCheck:
    """Check a single concentration value against its limit.

    Returns BREACH if over limit, WARNING if within buffer, OK otherwise.
    """
    excess = round(nav_pct - limit, 2)
    buffer = round(limit - nav_pct, 2)

    if nav_pct > limit:
        status = BreachStatus.BREACH
    elif nav_pct >= (limit - warning_buffer):
        status = BreachStatus.WARNING
    else:
        status = BreachStatus.OK

    return ConcentrationCheck(
        entity=entity,
        concentration_type=concentration_type,
        nav_pct=round(nav_pct, 2),
        limit=limit,
        status=status,
        excess_pct=max(excess, 0),
        buffer_pct=max(buffer, 0),
    )


def check_issuer_concentration(
    positions: List[dict],
    total_nav: float,
    limit: float,
    warning_buffer: float,
) -> List[ConcentrationCheck]:
    """Check each issuer's weight against the single-issuer limit.

    Args:
        positions: List of position dicts with 'name' and 'market_value'
        total_nav: Total portfolio NAV
        limit: Single issuer concentration limit (%)
        warning_buffer: Warning buffer (%)

    Returns:
        List of ConcentrationCheck results (only non-OK results + top 5 issuers)
    """
    if total_nav <= 0:
        return []

    # Aggregate by issuer name (netting long/short positions)
    issuer_values: Dict[str, float] = defaultdict(float)
    for pos in positions:
        val = pos.get("market_value", 0.0)
        # Netting: subtract exposure if position_type is short
        if str(pos.get("position_type", "long")).lower() == "short":
            issuer_values[pos.get("name", "Unknown")] -= val
        else:
            issuer_values[pos.get("name", "Unknown")] += val

    results = []
    for issuer, value in sorted(issuer_values.items(), key=lambda x: -abs(x[1])):
        nav_pct = (abs(value) / total_nav) * 100
        entity_name = f"{issuer} (Net Short)" if value < 0 else issuer
        check = _check_concentration(
            entity=entity_name,
            nav_pct=nav_pct,
            limit=limit,
            warning_buffer=warning_buffer,
            concentration_type=ConcentrationType.ISSUER,
        )
        results.append(check)

    return results


def check_sector_concentration(
    positions: List[dict],
    total_nav: float,
    limit: float,
    warning_buffer: float,
) -> List[ConcentrationCheck]:
    """Check sector-level concentration."""
    if total_nav <= 0:
        return []

    # Aggregate by sector name (netting long/short positions)
    sector_values: Dict[str, float] = defaultdict(float)
    for pos in positions:
        sector = pos.get("sector", "Unknown")
        val = pos.get("market_value", 0.0)
        if str(pos.get("position_type", "long")).lower() == "short":
            sector_values[sector] -= val
        else:
            sector_values[sector] += val

    results = []
    for sector, value in sorted(sector_values.items(), key=lambda x: -abs(x[1])):
        nav_pct = (abs(value) / total_nav) * 100
        entity_name = f"{sector} (Net Short)" if value < 0 else sector
        check = _check_concentration(
            entity=entity_name,
            nav_pct=nav_pct,
            limit=limit,
            warning_buffer=warning_buffer,
            concentration_type=ConcentrationType.SECTOR,
        )
        results.append(check)

    return results


def check_geography_concentration(
    positions: List[dict],
    total_nav: float,
    limit: float,
    warning_buffer: float,
) -> List[ConcentrationCheck]:
    """Check geography/country-level concentration."""
    if total_nav <= 0:
        return []

    # Aggregate by country name (netting long/short positions)
    country_values: Dict[str, float] = defaultdict(float)
    for pos in positions:
        country = pos.get("country", "Unknown")
        val = pos.get("market_value", 0.0)
        if str(pos.get("position_type", "long")).lower() == "short":
            country_values[country] -= val
        else:
            country_values[country] += val

    results = []
    for country, value in sorted(country_values.items(), key=lambda x: -abs(x[1])):
        nav_pct = (abs(value) / total_nav) * 100
        entity_name = f"{country} (Net Short)" if value < 0 else country
        check = _check_concentration(
            entity=entity_name,
            nav_pct=nav_pct,
            limit=limit,
            warning_buffer=warning_buffer,
            concentration_type=ConcentrationType.GEOGRAPHY,
        )
        results.append(check)

    return results


def check_asset_class_concentration(
    positions: List[dict],
    total_nav: float,
    limit: float,
    warning_buffer: float,
) -> List[ConcentrationCheck]:
    """Check asset class level concentration."""
    if total_nav <= 0:
        return []

    # Aggregate by asset class name (netting long/short positions)
    class_values: Dict[str, float] = defaultdict(float)
    for pos in positions:
        asset_class = pos.get("asset_class", "unknown")
        val = pos.get("market_value", 0.0)
        if str(pos.get("position_type", "long")).lower() == "short":
            class_values[asset_class] -= val
        else:
            class_values[asset_class] += val

    results = []
    for asset_class, value in sorted(class_values.items(), key=lambda x: -abs(x[1])):
        nav_pct = (abs(value) / total_nav) * 100
        entity_name = f"{asset_class} (Net Short)" if value < 0 else asset_class
        check = _check_concentration(
            entity=entity_name,
            nav_pct=nav_pct,
            limit=limit,
            warning_buffer=warning_buffer,
            concentration_type=ConcentrationType.ASSET_CLASS,
        )
        results.append(check)

    return results


def run_all_concentration_checks(
    positions: List[dict],
    total_nav: float,
    limits: RiskLimits,
    warning_buffer: float,
) -> RuleEngineResults:
    """Run ALL concentration checks and aggregate results.

    This is the main entry point for the rule engine. It:
    1. Checks issuer concentration
    2. Checks sector concentration
    3. Checks geography concentration
    4. Checks asset class concentration
    5. Counts total breaches and warnings

    Args:
        positions: List of position dicts
        total_nav: Total portfolio NAV
        limits: Configured risk limits
        warning_buffer: Warning buffer percentage

    Returns:
        RuleEngineResults with all check results
    """
    logger.info(
        "Running concentration checks",
        total_nav=total_nav,
        position_count=len(positions),
    )

    issuer_checks = check_issuer_concentration(
        positions, total_nav, limits.single_issuer_max, warning_buffer
    )
    sector_checks = check_sector_concentration(
        positions, total_nav, limits.sector_max, warning_buffer
    )
    geography_checks = check_geography_concentration(
        positions, total_nav, limits.geography_max, warning_buffer
    )
    asset_class_checks = check_asset_class_concentration(
        positions, total_nav, limits.asset_class_max, warning_buffer
    )

    # Count breaches and warnings across all checks
    all_checks = issuer_checks + sector_checks + geography_checks + asset_class_checks
    total_breaches = sum(1 for c in all_checks if c.status == BreachStatus.BREACH)
    total_warnings = sum(1 for c in all_checks if c.status == BreachStatus.WARNING)

    logger.info(
        "Concentration checks complete",
        total_breaches=total_breaches,
        total_warnings=total_warnings,
    )

    return RuleEngineResults(
        issuer_checks=issuer_checks,
        sector_checks=sector_checks,
        geography_checks=geography_checks,
        asset_class_checks=asset_class_checks,
        correlation_clusters=[],  # Filled by correlation_rules.py
        total_breaches=total_breaches,
        total_warnings=total_warnings,
    )

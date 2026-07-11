"""
RiskLens AI — Severity Classification Rules
Maps breach patterns to severity levels using deterministic logic.
Claude refines this with contextual analysis.
"""

from app.domain.enums import Severity, BreachStatus
from app.domain.models.risk import RuleEngineResults
from app.core.logger import get_logger

logger = get_logger("rules.severity")


def calculate_base_severity(results: RuleEngineResults) -> Severity:
    """Calculate baseline severity from rule engine results.

    Severity escalation logic:
      CRITICAL: 2+ breaches OR any issuer breach > 3% over limit
      HIGH:     1 breach
      MEDIUM:   Warnings only (approaching limits)
      LOW:      No breaches, no warnings, possibly minor flags

    Args:
        results: Output from the concentration rules engine

    Returns:
        Base severity level before Claude refinement
    """
    total_breaches = results.total_breaches
    total_warnings = results.total_warnings
    has_correlation_flags = len(results.correlation_clusters) > 0

    # Check for severe issuer breaches (> 3% over limit)
    severe_issuer_breach = False
    for check in results.issuer_checks:
        if check.status == BreachStatus.BREACH and check.excess_pct > 3.0:
            severe_issuer_breach = True
            break

    # Severity escalation
    if total_breaches >= 2 or severe_issuer_breach:
        severity = Severity.CRITICAL
    elif total_breaches >= 1:
        severity = Severity.HIGH
    elif total_warnings >= 1 or has_correlation_flags:
        severity = Severity.MEDIUM
    else:
        severity = Severity.LOW

    # Correlation clusters can escalate by one level
    if has_correlation_flags and severity in (Severity.LOW, Severity.MEDIUM):
        severity = Severity(min(
            Severity.HIGH.value,
            {"LOW": "MEDIUM", "MEDIUM": "HIGH"}.get(severity.value, severity.value)
        ))

    logger.info(
        "Base severity calculated",
        severity=severity.value,
        breaches=total_breaches,
        warnings=total_warnings,
        correlation_flags=len(results.correlation_clusters),
    )

    return severity

"""
RiskLens AI — Risk Analysis Service
Core orchestration service that ties together:
  Rule Engine → Claude AI → Severity Scoring → Notifications → Audit
"""

import time
import uuid
from datetime import datetime
from typing import Optional, Dict, Any

from app.core.logger import get_logger
from app.core.constants import ESCALATION_MATRIX
from app.domain.enums import (
    Severity, BreachStatus, ConcentrationType,
    AlertStatus, AssessmentTrigger, NotificationChannel, NotificationStatus,
)
from app.domain.models.risk import RuleEngineResults, ClaudeAnalysis, ModelInfo
from app.domain.models.audit import RiskLimits
from app.domain.rules.concentration_rules import run_all_concentration_checks
from app.domain.rules.correlation_rules import compute_correlation_matrix, detect_correlation_clusters
from app.domain.rules.severity_rules import calculate_base_severity
from app.infrastructure.ai.claude_client import get_claude_client
from app.infrastructure.external.yahoo_finance import get_yahoo_client
from app.infrastructure.database.repositories.portfolio_repo import PortfolioRepository, PositionRepository
from app.infrastructure.database.repositories.assessment_repo import (
    AssessmentRepository, AlertRepository, AuditRepository, ConfigRepository,
)
from app.infrastructure.websocket.manager import ws_manager
from app.services.notification_service import NotificationService

logger = get_logger("services.risk_analysis")


class RiskAnalysisService:
    """Orchestrates the complete risk analysis pipeline.

    Pipeline:
    1. Fetch portfolio + positions
    2. Fetch/update market prices from Yahoo Finance
    3. Run rule-based concentration checks
    4. Run correlation analysis
    5. Call Claude for AI analysis + rationale
    6. Generate severity verdict
    7. Create alerts for breaches
    8. Trigger notifications based on severity
    9. Log everything to audit trail
    """

    @staticmethod
    async def analyze_portfolio(
        portfolio_id: str,
        trigger: AssessmentTrigger = AssessmentTrigger.MANUAL,
    ) -> dict:
        """Run complete risk analysis on a portfolio.

        Args:
            portfolio_id: ID of the portfolio to analyze
            trigger: What triggered this analysis

        Returns:
            Complete assessment result as dict
        """
        start_time = time.time()
        assessment_id = f"ASSESS-{portfolio_id}-{uuid.uuid4().hex[:8]}"

        logger.info("Starting risk analysis", portfolio_id=portfolio_id, trigger=trigger.value)

        # --- Step 1: Fetch portfolio and positions ---
        portfolio = await PortfolioRepository.get_by_id(portfolio_id)
        if not portfolio:
            raise ValueError(f"Portfolio not found: {portfolio_id}")

        positions = await PositionRepository.get_by_portfolio(portfolio_id)
        if not positions:
            raise ValueError(f"No positions found for portfolio: {portfolio_id}")

        # --- Step 2: Update market prices ---
        symbols = [p.get("symbol") for p in positions if p.get("symbol") and p.get("asset_class") != "cash"]
        if symbols:
            try:
                yahoo = get_yahoo_client()
                prices = yahoo.get_current_prices(symbols)
                for pos in positions:
                    sym = pos.get("symbol")
                    if sym in prices and prices[sym]["price"] > 0:
                        pos["current_price"] = prices[sym]["price"]
                        pos["market_value"] = pos.get("quantity", 0) * prices[sym]["price"]
                        await PositionRepository.update_price(sym, portfolio_id, prices[sym]["price"])
            except Exception as e:
                logger.warning("Failed to update market prices, using cached", error=str(e))

        # Recalculate NAV and percentages
        total_nav = sum(p.get("market_value", 0) for p in positions)
        if total_nav > 0:
            for pos in positions:
                pos["nav_percentage"] = round((pos.get("market_value", 0) / total_nav) * 100, 2)

        await PortfolioRepository.update(portfolio_id, {"total_nav": total_nav})

        # --- Step 3: Get risk limits ---
        config = await ConfigRepository.get_or_default(portfolio_id)
        limits = RiskLimits(**config.get("limits", {}))
        warning_buffer = config.get("warning_buffer_pct", 3.0)

        # --- Step 4: Run rule-based concentration checks ---
        positions_dicts = [p for p in positions]
        rule_results = run_all_concentration_checks(
            positions=positions_dicts,
            total_nav=total_nav,
            limits=limits,
            warning_buffer=warning_buffer,
        )

        # --- Step 5: Run correlation analysis ---
        equity_symbols = [p["symbol"] for p in positions if p.get("asset_class") == "equity" and p.get("symbol")]
        if len(equity_symbols) >= 3:
            try:
                yahoo = get_yahoo_client()
                returns = yahoo.get_historical_returns(equity_symbols, days=30)
                corr_matrix = compute_correlation_matrix(returns)
                clusters = detect_correlation_clusters(corr_matrix, limits.correlation_threshold)
                rule_results.correlation_clusters = clusters
            except Exception as e:
                logger.warning("Correlation analysis failed", error=str(e))

        # --- Step 6: Call Claude for AI analysis ---
        claude_analysis: Optional[ClaudeAnalysis] = None
        model_info = ModelInfo()

        # Only call Claude if there are breaches, warnings, or flags
        needs_ai = (
            rule_results.total_breaches > 0
            or rule_results.total_warnings > 0
            or len(rule_results.correlation_clusters) > 0
        )

        if needs_ai:
            try:
                # Build market context for Claude
                market_context = {}
                if symbols:
                    try:
                        yahoo = get_yahoo_client()
                        # Get volatility for top holdings
                        top_symbols = [p["symbol"] for p in sorted(positions, key=lambda x: -x.get("nav_percentage", 0))[:5] if p.get("symbol") and p.get("asset_class") != "cash"]
                        for sym in top_symbols[:3]:
                            vol = yahoo.get_volatility(sym)
                            if vol["volatility_30d"] > 0:
                                market_context[sym] = vol
                    except Exception:
                        pass

                portfolio_context = {
                    "portfolio_id": portfolio_id,
                    "fund_name": portfolio.get("fund_name"),
                    "fund_type": portfolio.get("fund_type"),
                    "total_nav": total_nav,
                    "currency": portfolio.get("currency", "INR"),
                    "position_count": len(positions),
                    "timestamp": datetime.utcnow().isoformat(),
                }

                claude = get_claude_client()
                claude_analysis, model_info = await claude.analyze_portfolio_risk(
                    portfolio_context=portfolio_context,
                    rule_engine_results=rule_results.model_dump(),
                    market_context=market_context,
                )
            except Exception as e:
                logger.error("Claude analysis failed, using rule-based fallback", error=str(e))
                base_severity = calculate_base_severity(rule_results)
                claude_analysis = ClaudeAnalysis(
                    severity=base_severity,
                    confidence=0.5,
                    rationale="AI analysis unavailable. Rule-based assessment applied.",
                    overall_verdict=f"{base_severity.value} RISK — Rule-based assessment",
                )
        else:
            claude_analysis = ClaudeAnalysis(
                severity=Severity.LOW,
                confidence=0.95,
                rationale="All concentration limits within acceptable ranges. No breaches or warnings detected.",
                overall_verdict="LOW RISK — All limits compliant",
            )

        # --- Step 7: Build and store assessment ---
        elapsed_ms = int((time.time() - start_time) * 1000)
        assessment = {
            "_id": assessment_id,
            "portfolio_id": portfolio_id,
            "timestamp": datetime.utcnow().isoformat(),
            "trigger": trigger.value,
            "status": "completed",
            "nav_at_assessment": total_nav,
            "rule_engine_results": rule_results.model_dump(),
            "claude_analysis": claude_analysis.model_dump() if claude_analysis else None,
            "model_info": model_info.model_dump(),
            "processing_time_ms": elapsed_ms,
        }

        await AssessmentRepository.create(assessment)

        # --- Step 8: Create alerts for breaches ---
        alerts_created = []
        if claude_analysis and claude_analysis.severity in (Severity.MEDIUM, Severity.HIGH, Severity.CRITICAL):
            all_checks = (
                rule_results.issuer_checks +
                rule_results.sector_checks +
                rule_results.geography_checks +
                rule_results.asset_class_checks
            )

            for check in all_checks:
                if check.status in (BreachStatus.BREACH, BreachStatus.WARNING):
                    alert_id = f"ALERT-{portfolio_id}-{uuid.uuid4().hex[:8]}"
                    alert = {
                        "_id": alert_id,
                        "assessment_id": assessment_id,
                        "portfolio_id": portfolio_id,
                        "severity": claude_analysis.severity.value,
                        "title": f"{check.concentration_type.value.replace('_', ' ').title()} — {check.entity}",
                        "summary": f"{check.entity} at {check.nav_pct}% NAV (limit: {check.limit}%). {'BREACH' if check.status == BreachStatus.BREACH else 'WARNING'}.",
                        "breach_type": check.concentration_type.value,
                        "breach_details": {
                            "entity": check.entity,
                            "current_value": check.nav_pct,
                            "limit_value": check.limit,
                            "excess": check.excess_pct,
                        },
                        "status": AlertStatus.ACTIVE.value,
                        "created_at": datetime.utcnow().isoformat(),
                        "notifications_sent": [],
                    }
                    await AlertRepository.create(alert)
                    alerts_created.append(alert)

        # --- Step 9: Trigger notifications ---
        if claude_analysis and alerts_created:
            severity_str = claude_analysis.severity.value
            channels = ESCALATION_MATRIX.get(severity_str, [])
            notification_svc = NotificationService()

            for alert in alerts_created:
                for channel in channels:
                    await notification_svc.send_notification(
                        alert=alert,
                        assessment=assessment,
                        channel=channel,
                        portfolio=portfolio,
                    )

        # --- Step 10: Audit log ---
        audit_entry = {
            "_id": f"AUDIT-{uuid.uuid4().hex[:8]}",
            "timestamp": datetime.utcnow().isoformat(),
            "action": "risk_assessment_completed",
            "actor": "system",
            "portfolio_id": portfolio_id,
            "assessment_id": assessment_id,
            "details": {
                "trigger": trigger.value,
                "result_severity": claude_analysis.severity.value if claude_analysis else "UNKNOWN",
                "breaches_found": rule_results.total_breaches,
                "warnings_found": rule_results.total_warnings,
                "correlation_clusters": len(rule_results.correlation_clusters),
                "alerts_created": len(alerts_created),
                "processing_time_ms": elapsed_ms,
            },
        }
        await AuditRepository.create(audit_entry)

        # --- Step 11: WebSocket broadcast ---
        await ws_manager.broadcast_assessment({
            "assessment_id": assessment_id,
            "portfolio_id": portfolio_id,
            "severity": claude_analysis.severity.value if claude_analysis else "UNKNOWN",
            "breaches": rule_results.total_breaches,
            "warnings": rule_results.total_warnings,
            "alerts_count": len(alerts_created),
        })

        for alert in alerts_created:
            await ws_manager.broadcast_alert(alert)

        logger.info(
            "Risk analysis complete",
            portfolio_id=portfolio_id,
            severity=claude_analysis.severity.value if claude_analysis else "N/A",
            breaches=rule_results.total_breaches,
            warnings=rule_results.total_warnings,
            alerts=len(alerts_created),
            elapsed_ms=elapsed_ms,
        )

        return assessment

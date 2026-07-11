"""
RiskLens AI — Risk Analysis API Endpoints
"""

from fastapi import APIRouter, HTTPException, Query
from typing import Optional
from app.services.risk_analysis_service import RiskAnalysisService
from app.domain.enums import AssessmentTrigger
from app.infrastructure.database.repositories.assessment_repo import AssessmentRepository

router = APIRouter()


@router.post("/analyze/{portfolio_id}")
async def analyze_portfolio(portfolio_id: str):
    """Trigger risk analysis for a portfolio.

    Runs the complete pipeline:
    1. Fetch positions + update prices
    2. Rule engine concentration checks
    3. Claude AI analysis + rationale
    4. Severity scoring
    5. Alert creation + notification dispatch
    6. Audit logging
    """
    try:
        assessment = await RiskAnalysisService.analyze_portfolio(
            portfolio_id=portfolio_id,
            trigger=AssessmentTrigger.MANUAL,
        )

        claude_analysis = assessment.get("claude_analysis", {})
        rule_results = assessment.get("rule_engine_results", {})

        # Build response with key fields
        breaches = []
        warnings = []
        for check_type in ["issuer_checks", "sector_checks", "geography_checks", "asset_class_checks"]:
            for check in rule_results.get(check_type, []):
                if check.get("status") == "BREACH":
                    breaches.append(check)
                elif check.get("status") == "WARNING":
                    warnings.append(check)

        return {
            "assessment_id": assessment["_id"],
            "portfolio_id": portfolio_id,
            "severity": claude_analysis.get("severity", "UNKNOWN"),
            "confidence": claude_analysis.get("confidence", 0),
            "rationale": claude_analysis.get("rationale", ""),
            "overall_verdict": claude_analysis.get("overall_verdict", ""),
            "breaches": breaches,
            "warnings": warnings,
            "correlation_clusters": rule_results.get("correlation_clusters", []),
            "recommended_actions": claude_analysis.get("recommended_actions", []),
            "estimated_review_time_minutes": claude_analysis.get("estimated_review_time_minutes", 15),
            "processing_time_ms": assessment.get("processing_time_ms", 0),
        }

    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Risk analysis failed: {str(e)}")


@router.get("/assessments/{portfolio_id}")
async def list_assessments(
    portfolio_id: str,
    severity: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
):
    """List assessment history for a portfolio."""
    assessments, total = await AssessmentRepository.list_by_portfolio(
        portfolio_id=portfolio_id, severity=severity, page=page, limit=limit,
    )
    return {"assessments": assessments, "total": total, "page": page, "limit": limit}


@router.get("/assessments/{portfolio_id}/latest")
async def get_latest_assessment(portfolio_id: str):
    """Get the most recent assessment for a portfolio."""
    assessment = await AssessmentRepository.get_latest(portfolio_id)
    if not assessment:
        raise HTTPException(status_code=404, detail="No assessments found")
    return assessment

"""
RiskLens AI — Alert API Endpoints
"""

from fastapi import APIRouter, HTTPException, Query
from typing import Optional
from pydantic import BaseModel
from app.infrastructure.database.repositories.assessment_repo import AlertRepository, AssessmentRepository

router = APIRouter()


class AcknowledgeRequest(BaseModel):
    acknowledged_by: str
    notes: str = ""


@router.get("")
async def list_alerts(
    portfolio_id: Optional[str] = Query(None),
    severity: Optional[str] = Query(None, description="Comma-separated: HIGH,CRITICAL"),
    status: Optional[str] = Query(None, description="active, acknowledged, resolved"),
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200),
):
    """List alerts with optional filtering."""
    alerts, total = await AlertRepository.list_alerts(
        portfolio_id=portfolio_id, severity=severity, status=status,
        page=page, limit=limit,
    )
    return {"alerts": alerts, "total": total, "page": page, "limit": limit}


@router.get("/{alert_id}")
async def get_alert(alert_id: str):
    """Get alert detail with full assessment and notifications."""
    alert = await AlertRepository.get_by_id(alert_id)
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")

    assessment = await AssessmentRepository.get_by_id(alert.get("assessment_id", ""))

    return {
        "alert": alert,
        "assessment": assessment,
    }


@router.patch("/{alert_id}/acknowledge")
async def acknowledge_alert(alert_id: str, body: AcknowledgeRequest):
    """Acknowledge an alert."""
    success = await AlertRepository.acknowledge(
        alert_id=alert_id,
        acknowledged_by=body.acknowledged_by,
        notes=body.notes,
    )
    if not success:
        raise HTTPException(status_code=404, detail="Alert not found")

    return {"alert_id": alert_id, "status": "acknowledged", "acknowledged_by": body.acknowledged_by}

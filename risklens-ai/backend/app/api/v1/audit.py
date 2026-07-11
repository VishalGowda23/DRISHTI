"""
RiskLens AI — Audit Log API Endpoints
"""

from fastapi import APIRouter, Query
from typing import Optional
from app.infrastructure.database.repositories.assessment_repo import AuditRepository

router = APIRouter()


@router.get("/logs")
async def list_audit_logs(
    portfolio_id: Optional[str] = Query(None),
    action: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200),
):
    """Query audit logs with optional filtering."""
    logs, total = await AuditRepository.list_logs(
        portfolio_id=portfolio_id, action=action,
        page=page, limit=limit,
    )
    return {"logs": logs, "total": total, "page": page, "limit": limit}

"""
RiskLens AI — Configuration API Endpoints
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from app.infrastructure.database.repositories.assessment_repo import ConfigRepository
from app.core.constants import DEFAULT_RISK_LIMITS, DEFAULT_WARNING_BUFFER_PCT

router = APIRouter()


class RiskLimitsUpdate(BaseModel):
    limits: dict = Field(default_factory=lambda: DEFAULT_RISK_LIMITS)
    warning_buffer_pct: float = DEFAULT_WARNING_BUFFER_PCT


@router.get("/risk-limits/{portfolio_id}")
async def get_risk_limits(portfolio_id: str):
    """Get risk limits for a portfolio."""
    config = await ConfigRepository.get_or_default(portfolio_id)
    return config


@router.put("/risk-limits/{portfolio_id}")
async def update_risk_limits(portfolio_id: str, body: RiskLimitsUpdate):
    """Update risk limits for a portfolio."""
    config = {
        "portfolio_id": portfolio_id,
        "limits": body.limits,
        "warning_buffer_pct": body.warning_buffer_pct,
        "is_default": False,
        "updated_by": "api",
    }
    await ConfigRepository.upsert_limits(portfolio_id, config)
    return {"message": "Risk limits updated", "portfolio_id": portfolio_id}

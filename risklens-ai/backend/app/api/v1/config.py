"""
RiskLens AI — Configuration API Endpoints
"""

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from app.infrastructure.database.repositories.assessment_repo import ConfigRepository
from app.core.constants import DEFAULT_RISK_LIMITS, DEFAULT_WARNING_BUFFER_PCT
from app.api.dependencies import verify_cro_role

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
async def update_risk_limits(
    portfolio_id: str,
    body: RiskLimitsUpdate,
    role: str = Depends(verify_cro_role),
):
    """Update risk limits for a portfolio. Restricted to CRO and ADMIN roles."""
    config = {
        "portfolio_id": portfolio_id,
        "limits": body.limits,
        "warning_buffer_pct": body.warning_buffer_pct,
        "is_default": False,
        "updated_by": f"api:{role.lower()}",
    }
    await ConfigRepository.upsert_limits(portfolio_id, config)
    return {"message": f"Risk limits updated by {role}", "portfolio_id": portfolio_id}

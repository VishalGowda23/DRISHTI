"""
RiskLens AI — Audit & Configuration Domain Models
"""

from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from datetime import datetime
from app.core.constants import DEFAULT_RISK_LIMITS, DEFAULT_WARNING_BUFFER_PCT


class RiskLimits(BaseModel):
    """Configurable risk limits for a portfolio."""
    single_issuer_max: float = DEFAULT_RISK_LIMITS["single_issuer_max"]
    sector_max: float = DEFAULT_RISK_LIMITS["sector_max"]
    geography_max: float = DEFAULT_RISK_LIMITS["geography_max"]
    asset_class_max: float = DEFAULT_RISK_LIMITS["asset_class_max"]
    correlation_threshold: float = DEFAULT_RISK_LIMITS["correlation_threshold"]
    min_holdings: int = DEFAULT_RISK_LIMITS["min_holdings"]
    max_cash_percentage: float = DEFAULT_RISK_LIMITS["max_cash_percentage"]


class RiskLimitConfig(BaseModel):
    """Risk limit configuration for a specific portfolio."""
    id: str = Field(..., alias="_id")
    portfolio_id: str
    limits: RiskLimits = RiskLimits()
    warning_buffer_pct: float = DEFAULT_WARNING_BUFFER_PCT
    is_default: bool = True
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_by: str = "system"

    model_config = {"populate_by_name": True}


class AuditLog(BaseModel):
    """Immutable audit log entry."""
    id: str = Field(..., alias="_id")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    action: str = Field(..., description="e.g., risk_assessment_completed, alert_created")
    actor: str = Field(default="system", description="User or system that performed the action")
    portfolio_id: Optional[str] = None
    assessment_id: Optional[str] = None
    alert_id: Optional[str] = None
    details: Dict[str, Any] = {}
    request_metadata: Dict[str, Any] = {}

    model_config = {"populate_by_name": True}


class MarketDataPoint(BaseModel):
    """A single market data snapshot for a symbol."""
    id: str = Field(..., alias="_id")
    symbol: str
    price: float
    previous_close: float = 0.0
    day_change_pct: float = 0.0
    volume: int = 0
    volatility_30d: float = 0.0
    volatility_30d_prev_quarter: float = 0.0
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    source: str = "yahoo_finance"

    model_config = {"populate_by_name": True}

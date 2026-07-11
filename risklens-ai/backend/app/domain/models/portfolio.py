"""
RiskLens AI — Portfolio Domain Models
Core domain models for portfolios and positions.
"""

from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from datetime import datetime
from app.domain.enums import AssetClass, PortfolioStatus


class PositionMetadata(BaseModel):
    """Additional metadata for a position."""
    isin: Optional[str] = None
    exchange: Optional[str] = None
    lot_size: int = 1


class Position(BaseModel):
    """A single holding within a portfolio."""
    id: str = Field(..., alias="_id", description="Position ID, e.g., POS-001-RIL")
    portfolio_id: str
    symbol: str = Field(..., description="Ticker symbol, e.g., RELIANCE.NS")
    name: str = Field(..., description="Full company/instrument name")
    asset_class: AssetClass
    sector: str
    country: str
    quantity: float
    avg_cost_price: float = 0.0
    current_price: float = 0.0
    market_value: float = 0.0
    nav_percentage: float = 0.0
    currency: str = "INR"
    last_price_update: Optional[datetime] = None
    metadata: PositionMetadata = PositionMetadata()

    model_config = {"populate_by_name": True}


class PortfolioMetadata(BaseModel):
    """Additional metadata for a portfolio."""
    account_id: Optional[str] = None
    benchmark: Optional[str] = None
    inception_date: Optional[str] = None


class Portfolio(BaseModel):
    """A portfolio / fund containing multiple positions."""
    id: str = Field(..., alias="_id", description="Portfolio ID, e.g., PORT-2026-0442")
    fund_name: str
    fund_type: str = "Multi-Asset"
    manager: Optional[str] = None
    currency: str = "INR"
    status: PortfolioStatus = PortfolioStatus.ACTIVE
    total_nav: float = 0.0
    positions_count: int = 0
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    metadata: PortfolioMetadata = PortfolioMetadata()

    model_config = {"populate_by_name": True}

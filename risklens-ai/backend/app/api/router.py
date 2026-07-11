"""
RiskLens AI — API Router Aggregator
Collects all endpoint routers into a single API router.
"""

from fastapi import APIRouter
from app.api.v1 import portfolio, risk, alerts, config, audit, health, market

api_router = APIRouter()

api_router.include_router(health.router, prefix="/health", tags=["Health"])
api_router.include_router(portfolio.router, prefix="/portfolios", tags=["Portfolios"])
api_router.include_router(risk.router, prefix="/risk", tags=["Risk Analysis"])
api_router.include_router(alerts.router, prefix="/alerts", tags=["Alerts"])
api_router.include_router(config.router, prefix="/config", tags=["Configuration"])
api_router.include_router(audit.router, prefix="/audit", tags=["Audit"])
api_router.include_router(market.router, tags=["Market Data"])

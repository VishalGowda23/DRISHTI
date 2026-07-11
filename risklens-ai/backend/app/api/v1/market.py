"""
RiskLens AI — Market Data API Endpoints  (v1)
Exposes synthetic market data controls and shock triggers for demo / testing.

Endpoints
---------
GET  /market/prices          — Current in-memory mock prices for all NSE symbols
GET  /market/symbols         — Full symbol pool metadata (name, token, sector, country)
POST /market/shock           — Trigger an extreme price move on a single symbol
GET  /market/ping            — MongoDB connectivity check (kept from original data-mongo.py)
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

router = APIRouter(prefix="/market", tags=["Market Data"])


# ---------------------------------------------------------------------------
# Request / Response schemas
# ---------------------------------------------------------------------------

class ShockRequest(BaseModel):
    """Payload for the shock endpoint."""
    symbol: str = Field(..., description="NSE symbol without .NS suffix, e.g. RELIANCE")
    direction: str = Field("down", description="'up' or 'down'")
    magnitude_pct: float = Field(10.0, gt=0, le=100, description="Shock size as a percentage")


class ShockResponse(BaseModel):
    ok: bool
    symbol: str
    direction: str
    magnitude_pct: float
    shocked_price: float
    message: str


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.get("/prices", summary="Current mock prices for all NSE symbols")
async def get_prices():
    """Return the current in-memory price for every symbol in the mock pool.

    Prices are updated every 30 seconds by the mock price poller worker.
    """
    try:
        from app.workers.mock_price_poller import get_current_prices
        prices = await get_current_prices()
        return {"count": len(prices), "prices": prices}
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Price service unavailable: {exc}")


@router.get("/symbols", summary="Full NSE symbol pool metadata")
async def get_symbols():
    """Return the complete symbol pool including sector, country, and base prices."""
    from app.infrastructure.external.symbol_pool import SYMBOL_POOL
    return {"count": len(SYMBOL_POOL), "symbols": SYMBOL_POOL}


@router.post("/shock", response_model=ShockResponse, summary="Trigger an extreme price shock")
async def shock_endpoint(req: ShockRequest):
    """Apply an extreme price move to a single symbol and propagate it through the pipeline.

    The shock is published as a Kafka event (or written directly to MongoDB if Kafka is
    unavailable), just like a normal price tick — but tagged with ``source: "shock"``
    so it can be identified in the ``price_ticks`` time-series collection.

    This endpoint is used during demos to instantly trigger HIGH / CRITICAL alerts.

    Example::

        curl -X POST http://localhost:8000/api/v1/market/shock \\
          -H "Content-Type: application/json" \\
          -d '{"symbol": "RELIANCE", "direction": "down", "magnitude_pct": 12}'
    """
    from app.infrastructure.external.symbol_pool import get_symbol_meta

    if get_symbol_meta(req.symbol) is None:
        raise HTTPException(status_code=400, detail=f"Symbol '{req.symbol}' not found in pool")

    if req.direction not in ("up", "down"):
        raise HTTPException(status_code=400, detail="direction must be 'up' or 'down'")

    try:
        from app.workers.mock_price_poller import trigger_shock
        shocked_price = await trigger_shock(req.symbol, req.direction, req.magnitude_pct)
        return ShockResponse(
            ok=True,
            symbol=req.symbol,
            direction=req.direction,
            magnitude_pct=req.magnitude_pct,
            shocked_price=shocked_price,
            message=f"Shock applied: {req.symbol} {req.direction} {req.magnitude_pct}%",
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Shock failed: {exc}")


@router.get("/ping", summary="MongoDB connectivity check")
async def ping_db():
    """Ping MongoDB to verify the database connection is alive."""
    try:
        from app.infrastructure.database.mongodb import get_database
        db = get_database()
        await db.command("ping")
        return {"ok": True, "database": "connected"}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}

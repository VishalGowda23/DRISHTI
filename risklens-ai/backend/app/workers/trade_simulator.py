"""
RiskLens AI — Trade Simulator Worker
Simulates random portfolio mutations at 5–10 minute intervals to keep the
synthetic dataset "alive" during demos and development.

Three mutation types are applied at random:
- ADJUST_QUANTITY (70%): randomly change the quantity of an existing holding
- ADD_HOLDING    (20%): add a new symbol not already in the portfolio
- REMOVE_HOLDING (10%): remove a random holding (only if portfolio has > 4 holdings)

Every mutation is:
1. Applied to the in-memory portfolio document.
2. Written back to the ``portfolios`` MongoDB collection via upsert.
3. Logged to the ``trades`` collection for audit purposes.

Usage (standalone):
    python -m app.workers.trade_simulator

The worker is also started automatically by ``app/main.py`` during FastAPI startup.
"""

import asyncio
import random
import uuid
from datetime import datetime, timezone

from app.core.logger import get_logger
from app.infrastructure.database.mongodb import connect_to_mongodb, close_mongodb, get_database
from app.infrastructure.external.symbol_pool import SYMBOL_POOL, symbol_base_prices

logger = get_logger("workers.trade_simulator")

# Interval range between simulated trades (seconds)
_MIN_INTERVAL = 300   # 5 minutes
_MAX_INTERVAL = 600   # 10 minutes

# Portfolio holding count bounds
_MIN_HOLDINGS = 4
_MAX_HOLDINGS = 7


# ---------------------------------------------------------------------------
# Mutation helpers
# ---------------------------------------------------------------------------

def _adjust_quantity(holding: dict, current_prices: dict[str, float]) -> None:
    """Randomly adjust the quantity of an existing holding by ±20 units."""
    delta = random.randint(-20, 20)
    holding["quantity"] = max(1, holding["quantity"] + delta)
    holding["invested_value"] = round(holding["quantity"] * holding["average_price"], 2)
    holding["current_value"] = round(
        holding["quantity"] * current_prices.get(holding["symbol"], holding["current_price"]), 2
    )
    holding["pnl"] = round(holding["current_value"] - holding["invested_value"], 2)


def _add_holding(portfolio: dict, current_prices: dict[str, float]) -> bool:
    """Add a randomly chosen symbol that is not already in the portfolio.

    Returns True if a new holding was added, False if no symbols were available.
    """
    held_symbols = {h["symbol"] for h in portfolio["holdings"]}
    available = [s for s in SYMBOL_POOL if s["symbol"] not in held_symbols]
    if not available:
        return False

    sym = random.choice(available)
    price = current_prices.get(sym["symbol"], sym["base"])
    qty = random.randint(5, 50)
    avg = round(price * random.uniform(0.90, 1.10), 2)

    portfolio["holdings"].append(
        {
            "symbol": sym["symbol"],
            "instrument_token": sym["token"],
            "quantity": qty,
            "average_price": avg,
            "current_price": round(price, 2),
            "invested_value": round(qty * avg, 2),
            "current_value": round(qty * price, 2),
            "pnl": round(qty * (price - avg), 2),
            "portfolio_weight_percentage": 0.0,  # recalculated after
        }
    )
    return True


def _remove_holding(portfolio: dict) -> bool:
    """Remove a random holding. Only acts if portfolio has more than _MIN_HOLDINGS."""
    if len(portfolio["holdings"]) <= _MIN_HOLDINGS:
        return False
    idx = random.randint(0, len(portfolio["holdings"]) - 1)
    portfolio["holdings"].pop(idx)
    return True


def _recompute_agg(port: dict) -> None:
    """Recompute portfolio-level aggregates in-place."""
    port["total_invested"] = round(
        sum(h["quantity"] * h["average_price"] for h in port["holdings"]), 2
    )
    total_curr = sum(h["current_value"] for h in port["holdings"])
    for h in port["holdings"]:
        h["portfolio_weight_percentage"] = (
            round(h["current_value"] / total_curr * 100, 2) if total_curr > 0 else 0.0
        )
    port["portfolio_value"] = round(total_curr, 2)
    port["total_pnl"] = round(total_curr - port["total_invested"], 2)
    port["total_pnl_percentage"] = (
        round(port["total_pnl"] / port["total_invested"] * 100, 2)
        if port["total_invested"] > 0
        else 0.0
    )
    port["last_updated"] = datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# Worker loop
# ---------------------------------------------------------------------------

async def trade_simulator_worker() -> None:
    """Continuously simulate random trades on synthetic portfolios.

    Runs until cancelled (e.g. on FastAPI shutdown or asyncio.CancelledError).
    """
    # Maintain a live copy of "current prices" (updated lazily from price_ticks)
    current_prices: dict[str, float] = symbol_base_prices()

    logger.info(
        "Trade simulator worker started",
        interval_range_s=f"{_MIN_INTERVAL}–{_MAX_INTERVAL}",
    )

    while True:
        sleep_for = random.uniform(_MIN_INTERVAL, _MAX_INTERVAL)
        await asyncio.sleep(sleep_for)

        try:
            db = get_database()

            # Refresh current prices from the latest price_ticks
            try:
                pipeline = [
                    {"$sort": {"ts": -1}},
                    {"$group": {"_id": "$symbol", "price": {"$first": "$price"}}},
                ]
                async for doc in db["price_ticks"].aggregate(pipeline):
                    current_prices[doc["_id"]] = doc["price"]
            except Exception:
                pass  # fall back to base prices if time-series not available yet

            # Pick a random portfolio
            portfolios = await db["portfolios"].find({}).to_list(None)
            if not portfolios:
                continue
            port = random.choice(portfolios)

            # Choose action
            action = random.choices(
                ["ADJUST_QUANTITY", "ADD_HOLDING", "REMOVE_HOLDING"],
                weights=[0.70, 0.20, 0.10],
            )[0]

            acted = False
            if action == "ADJUST_QUANTITY" and port["holdings"]:
                h = random.choice(port["holdings"])
                _adjust_quantity(h, current_prices)
                acted = True
            elif action == "ADD_HOLDING" and len(port["holdings"]) < _MAX_HOLDINGS:
                acted = _add_holding(port, current_prices)
            elif action == "REMOVE_HOLDING":
                acted = _remove_holding(port)

            if not acted:
                continue

            _recompute_agg(port)

            # Write updated portfolio to MongoDB
            await db["portfolios"].update_one(
                {"portfolio_id": port["portfolio_id"]},
                {"$set": port},
            )

            # Append trade record to audit log
            await db["trades"].insert_one(
                {
                    "trade_id": str(uuid.uuid4()),
                    "portfolio_id": port["portfolio_id"],
                    "ts": datetime.now(timezone.utc),
                    "action": action,
                }
            )

            logger.info(
                "Simulated trade",
                action=action,
                portfolio_id=port["portfolio_id"],
            )

        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.error("Trade simulator error", error=str(exc))


# ---------------------------------------------------------------------------
# Standalone entry point
# ---------------------------------------------------------------------------

async def run_worker() -> None:
    """Entry point for running the trade simulator as a standalone process."""
    from app.core.logger import setup_logging
    setup_logging()
    await connect_to_mongodb()
    try:
        await trade_simulator_worker()
    finally:
        await close_mongodb()


if __name__ == "__main__":
    asyncio.run(run_worker())

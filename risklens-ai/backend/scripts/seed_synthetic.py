"""
RiskLens AI — Synthetic Portfolio Seeder
Seeds MongoDB with 10 synthetic portfolios using the NSE SYMBOL_POOL.
Each portfolio has 4–7 randomly selected holdings with randomised quantities
and average prices.  This complements the JSON-file seeder (seed_database.py)
with a fully in-memory dataset that requires no sample data files.

Usage:
    # From the backend/ directory:
    python scripts/seed_synthetic.py

    # Or as a module:
    python -m scripts.seed_synthetic

The seeder is idempotent: it checks whether ≥ 10 portfolios already exist
and skips seeding if so.  Use --force to re-seed even when data exists.
"""

import asyncio
import random
import sys
import os
import argparse
from datetime import datetime, timezone

# Allow importing app modules when running as a script from backend/
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.infrastructure.database.mongodb import connect_to_mongodb, close_mongodb, get_database
from app.infrastructure.external.symbol_pool import SYMBOL_POOL, symbol_base_prices
from app.core.logger import setup_logging, get_logger

logger = get_logger("scripts.seed_synthetic")

_N_PORTFOLIOS = 10
_MIN_HOLDINGS = 4
_MAX_HOLDINGS = 7


def _build_portfolio(index: int, current_prices: dict[str, float]) -> dict:
    """Build a single synthetic portfolio document."""
    uid = f"U{index:03d}"
    pid = f"P{index:03d}"

    n_hold = random.randint(_MIN_HOLDINGS, _MAX_HOLDINGS)
    chosen_syms = random.sample(SYMBOL_POOL, n_hold)

    holdings = []
    total_inv = 0.0
    total_curr = 0.0

    for sym in chosen_syms:
        curr_price = current_prices[sym["symbol"]]
        avg_price = round(curr_price * random.uniform(0.85, 1.15), 2)
        qty = random.randint(5, 100)
        inv_val = round(qty * avg_price, 2)
        curr_val = round(qty * curr_price, 2)

        holdings.append(
            {
                "symbol": sym["symbol"],
                "instrument_token": sym["token"],
                "sector": sym["sector"],
                "country": sym["country"],
                "quantity": qty,
                "average_price": avg_price,
                "current_price": curr_price,
                "invested_value": inv_val,
                "current_value": curr_val,
                "pnl": round(curr_val - inv_val, 2),
                "portfolio_weight_percentage": 0.0,  # filled below
            }
        )
        total_inv += inv_val
        total_curr += curr_val

    # Compute weight percentages
    for h in holdings:
        h["portfolio_weight_percentage"] = (
            round(h["current_value"] / total_curr * 100, 2) if total_curr > 0 else 0.0
        )

    return {
        "user_id": uid,
        "portfolio_id": pid,
        "broker": "ZERODHA",
        "portfolio_value": round(total_curr, 2),
        "total_invested": round(total_inv, 2),
        "total_pnl": round(total_curr - total_inv, 2),
        "total_pnl_percentage": (
            round((total_curr - total_inv) / total_inv * 100, 2) if total_inv > 0 else 0.0
        ),
        "holdings": holdings,
        "last_updated": datetime.now(timezone.utc),
    }


async def _setup_collections() -> None:
    """Ensure required collections and indexes exist.

    Creates the ``price_ticks`` time-series collection and
    all indexes on ``portfolios`` and ``trades``.
    """
    db = get_database()

    # Portfolios indexes
    col = db["portfolios"]
    await col.create_index([("portfolio_id", 1)], unique=True)
    await col.create_index([("user_id", 1)], unique=True)
    await col.create_index([("holdings.symbol", 1)])

    # Trades indexes
    await db["trades"].create_index([("portfolio_id", 1), ("ts", -1)])

    # Time-series collection for price ticks
    try:
        await db.create_collection(
            "price_ticks",
            timeseries={
                "timeField": "ts",
                "metaField": "symbol",
                "granularity": "minutes",
            },
        )
        logger.info("Created 'price_ticks' time-series collection")
    except Exception:
        pass  # Already exists — that's fine


async def seed(force: bool = False) -> None:
    """Seed the database with synthetic portfolios.

    Args:
        force: When True, drop existing synthetic portfolios and re-seed.
    """
    setup_logging()
    await connect_to_mongodb()
    db = get_database()

    await _setup_collections()

    existing = await db["portfolios"].count_documents({})
    if existing >= _N_PORTFOLIOS and not force:
        logger.info(
            "Portfolios already exist — skipping seed",
            count=existing,
            tip="Pass --force to re-seed",
        )
        await close_mongodb()
        return

    if force:
        deleted = await db["portfolios"].delete_many({})
        logger.info("Cleared existing portfolios", deleted=deleted.deleted_count)

    logger.info(f"Seeding {_N_PORTFOLIOS} synthetic portfolios...")
    current_prices = symbol_base_prices()

    for i in range(1, _N_PORTFOLIOS + 1):
        port = _build_portfolio(i, current_prices)
        await db["portfolios"].update_one(
            {"portfolio_id": port["portfolio_id"]},
            {"$set": port},
            upsert=True,
        )
        logger.info(f"  ✅ Seeded portfolio {port['portfolio_id']} ({len(port['holdings'])} holdings)")

    logger.info(f"🎉 Done! {_N_PORTFOLIOS} synthetic portfolios seeded.")
    await close_mongodb()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed RiskLens AI with synthetic portfolio data")
    parser.add_argument("--force", action="store_true", help="Drop and re-seed even if data exists")
    args = parser.parse_args()
    asyncio.run(seed(force=args.force))

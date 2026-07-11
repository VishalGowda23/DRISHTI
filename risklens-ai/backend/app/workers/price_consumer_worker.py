"""
RiskLens AI — Price Consumer Worker
Consumes ``stock-price-updates`` events from Kafka, writes price ticks to the
MongoDB time-series collection, and recomputes all portfolio aggregates that
hold the affected symbol.

This is the Kafka-consumer half of the data pipeline:

    Price Poller ──► Kafka ──► (this worker) ──► MongoDB
                                               ├── price_ticks  (time-series)
                                               └── portfolios   (recomputed)

Fallback: when Kafka is unavailable the market_data_worker writes directly to
MongoDB via ``apply_price_update`` without going through this consumer.

Usage (standalone):
    python -m app.workers.price_consumer_worker

The worker is also started automatically by ``app/main.py`` during FastAPI
startup when Kafka is reachable.
"""

import asyncio
from datetime import datetime, timezone

from app.core.logger import get_logger
from app.infrastructure.database.mongodb import connect_to_mongodb, close_mongodb, get_database
from app.infrastructure.kafka.consumer import consume_forever
from app.core.constants import TOPIC_MARKET_PRICES

logger = get_logger("workers.price_consumer")

CONSUMER_GROUP = "portfolio-recompute-group"


# ---------------------------------------------------------------------------
# Core price-application logic
# ---------------------------------------------------------------------------

async def apply_price_update(
    symbol: str,
    price: float,
    instrument_token: int,
    source: str = "poll",
) -> None:
    """Persist a price tick and recompute all portfolios holding that symbol.

    Steps:
    1. Insert a document into the ``price_ticks`` time-series collection.
    2. Find every portfolio document whose ``holdings`` array contains ``symbol``.
    3. For each matching portfolio, update ``current_price`` / ``current_value``
       / ``pnl`` on the relevant holding then call ``recompute_agg`` to refresh
       portfolio-level totals (value, PnL %, weight percentages).
    4. Upsert the updated portfolio back to MongoDB.

    Args:
        symbol: NSE symbol without the ``.NS`` suffix (e.g. ``"RELIANCE"``).
        price: New current price.
        instrument_token: Zerodha instrument token for the symbol.
        source: ``"poll"`` for routine polling, ``"shock"`` for shock events.
    """
    db = get_database()
    now = datetime.now(timezone.utc)

    # 1. Write price tick to time-series collection
    await db["price_ticks"].insert_one(
        {
            "ts": now,
            "symbol": symbol,
            "instrument_token": instrument_token,
            "price": price,
            "source": source,
        }
    )

    # 2. Find affected portfolios
    portfolios = await db["portfolios"].find({"holdings.symbol": symbol}).to_list(None)
    if not portfolios:
        return

    updated_count = 0
    for port in portfolios:
        changed = False
        for h in port["holdings"]:
            if h["symbol"] == symbol:
                h["current_price"] = price
                h["current_value"] = round(h["quantity"] * price, 2)
                h["pnl"] = round(h["current_value"] - h["invested_value"], 2)
                changed = True

        if changed:
            _recompute_agg(port)
            await db["portfolios"].update_one(
                {"portfolio_id": port["portfolio_id"]},
                {"$set": port},
            )
            updated_count += 1

    if updated_count:
        logger.info(
            "Price update applied",
            symbol=symbol,
            price=price,
            portfolios_updated=updated_count,
            source=source,
        )


def _recompute_agg(port: dict) -> dict:
    """Recompute portfolio-level aggregates in-place and return the document.

    Recalculates:
    - ``portfolio_value`` — sum of all current_values
    - ``portfolio_weight_percentage`` per holding
    - ``total_pnl`` and ``total_pnl_percentage``
    - ``last_updated`` timestamp
    """
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
    return port


# ---------------------------------------------------------------------------
# Kafka message handler
# ---------------------------------------------------------------------------

async def _handle_price_tick(payload: dict) -> None:
    """Process a single price-tick message from Kafka.

    Expected payload schema (mirrors what the price poller publishes)::

        {
            "event_id": "uuid",
            "symbol": "RELIANCE",
            "instrument_token": 738561,
            "price": 2467.50,
            "ts": "2026-07-11T09:15:00Z",
            "source": "poll"          # or "shock"
        }
    """
    symbol = payload.get("symbol")
    price = payload.get("price")
    token = payload.get("instrument_token", 0)
    source = payload.get("source", "poll")

    if not symbol or price is None:
        logger.warning("Received malformed price tick, skipping", payload=payload)
        return

    await apply_price_update(symbol, float(price), int(token), source)


# ---------------------------------------------------------------------------
# Worker entry point
# ---------------------------------------------------------------------------

async def price_consumer_worker() -> None:
    """Consume price ticks from Kafka and apply them to MongoDB.

    This coroutine runs indefinitely until cancelled (e.g. on FastAPI shutdown).
    """
    logger.info(
        "Price consumer worker starting",
        topic=TOPIC_MARKET_PRICES,
        group=CONSUMER_GROUP,
    )
    await consume_forever(
        TOPIC_MARKET_PRICES,
        group_id=CONSUMER_GROUP,
        handler=_handle_price_tick,
        auto_offset_reset="earliest",
    )


async def run_worker() -> None:
    """Standalone entry point (``python -m app.workers.price_consumer_worker``)."""
    from app.core.logger import setup_logging
    setup_logging()
    await connect_to_mongodb()
    try:
        await price_consumer_worker()
    finally:
        await close_mongodb()


if __name__ == "__main__":
    asyncio.run(run_worker())

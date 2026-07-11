"""
RiskLens AI — Mock Price Poller Worker
Generates synthetic price ticks for all NSE symbols in the pool by applying a
random ±3% walk every 30 seconds (configurable).  Publishes each tick to Kafka.
If Kafka is unavailable, falls back to writing directly to MongoDB via
``apply_price_update`` from the price consumer worker.

This worker supplements (or replaces) real Yahoo Finance polling during:
- Offline / development environments
- Outside Indian market hours (09:15–15:30 IST)
- Demo runs where we want controlled, predictable price movements

Data Flow:
    Mock Price Poller ──► publish_price()
                            ├── Kafka available ──► stock-price-updates topic
                            │                       └──► Price Consumer Worker ──► MongoDB
                            └── Kafka unavailable ──► apply_price_update() ──► MongoDB directly

Usage (standalone):
    python -m app.workers.mock_price_poller

The worker is also started automatically by ``app/main.py`` during FastAPI startup.
"""

import asyncio
import json
import uuid
import random
from datetime import datetime, timezone
from typing import Optional

from aiokafka import AIOKafkaProducer
from app.core.config import get_settings
from app.core.logger import get_logger
from app.core.constants import TOPIC_MARKET_PRICES
from app.infrastructure.database.mongodb import connect_to_mongodb, close_mongodb
from app.infrastructure.external.symbol_pool import SYMBOL_POOL, symbol_base_prices
from app.services.kafka_risk_service import on_price_tick as _risk_on_price_tick

logger = get_logger("workers.mock_price_poller")

# Tick interval in seconds (overridable via env MOCK_POLL_INTERVAL_SECONDS)
_DEFAULT_INTERVAL = 30
# Maximum random walk per tick: ±3%
_MAX_CHANGE = 0.03

# Module-level state — reset on each startup
_producer: Optional[AIOKafkaProducer] = None
_kafka_available: bool = False
_current_prices: dict[str, float] = {}


# ---------------------------------------------------------------------------
# Kafka helpers
# ---------------------------------------------------------------------------

async def _try_connect_kafka() -> bool:
    """Attempt to connect a Kafka producer. Returns True on success."""
    global _producer, _kafka_available
    settings = get_settings()
    try:
        _producer = AIOKafkaProducer(bootstrap_servers=settings.kafka_bootstrap_servers)
        await _producer.start()
        _kafka_available = True
        logger.info("Mock poller: Kafka producer connected")
        return True
    except Exception as exc:
        _producer = None
        _kafka_available = False
        logger.warning(
            "Mock poller: Kafka unavailable — falling back to direct MongoDB writes",
            error=str(exc),
        )
        return False


async def _publish_tick(symbol: str, price: float, token: int, source: str = "poll") -> None:
    """Publish a price tick to Kafka, or write directly to MongoDB on failure."""
    global _producer, _kafka_available

    if _kafka_available and _producer is not None:
        msg = {
            "event_id": str(uuid.uuid4()),
            "symbol": symbol,
            "instrument_token": token,
            "price": round(price, 2),
            "ts": datetime.now(timezone.utc).isoformat(),
            "source": source,
        }
        try:
            await _producer.send_and_wait(
                TOPIC_MARKET_PRICES,
                key=symbol.encode(),
                value=json.dumps(msg).encode(),
            )
            # Feed the risk model's return-series store on every successful publish
            _risk_on_price_tick(symbol, price)
            return
        except Exception as exc:
            logger.error(
                "Kafka publish failed — falling back to direct Mongo write",
                symbol=symbol,
                error=str(exc),
            )
            _kafka_available = False

    # Direct MongoDB write (no Kafka)
    from app.workers.price_consumer_worker import apply_price_update
    await apply_price_update(symbol, round(price, 2), token, source)
    # Feed the risk model's return-series store on the fallback path too
    _risk_on_price_tick(symbol, price)


# ---------------------------------------------------------------------------
# Worker loop
# ---------------------------------------------------------------------------

async def mock_price_poller_worker(interval_seconds: int = _DEFAULT_INTERVAL) -> None:
    """Emit synthetic price ticks for all symbols every ``interval_seconds``.

    The price walk uses a multiplicative random step:
        new_price = current_price * (1 + random.uniform(-MAX_CHANGE, MAX_CHANGE))

    Args:
        interval_seconds: Seconds between full-batch tick publications.
    """
    global _current_prices

    # Initialise prices from base values
    _current_prices = symbol_base_prices()

    await _try_connect_kafka()

    logger.info(
        "Mock price poller started",
        symbols=len(SYMBOL_POOL),
        interval_s=interval_seconds,
        kafka=_kafka_available,
    )

    while True:
        try:
            for sym in SYMBOL_POOL:
                symbol = sym["symbol"]
                change = random.uniform(-_MAX_CHANGE, _MAX_CHANGE)
                _current_prices[symbol] = round(_current_prices[symbol] * (1 + change), 2)
                await _publish_tick(symbol, _current_prices[symbol], sym["token"], "poll")

            logger.info(
                "Mock tick batch published",
                count=len(SYMBOL_POOL),
                kafka=_kafka_available,
            )

        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.error("Mock price poller error", error=str(exc))

        await asyncio.sleep(interval_seconds)


async def trigger_shock(symbol: str, direction: str = "down", magnitude_pct: float = 10.0) -> float:
    """Apply an extreme price shock to a single symbol.

    Used by the ``/shock`` API endpoint to simulate market stress events.

    Args:
        symbol: NSE symbol (e.g. ``"RELIANCE"``).
        direction: ``"up"`` or ``"down"``.
        magnitude_pct: Size of the shock as a percentage (e.g. 12 for 12%).

    Returns:
        The new shocked price.

    Raises:
        ValueError: If the symbol is not in the pool.
    """
    from app.infrastructure.external.symbol_pool import get_symbol_meta
    meta = get_symbol_meta(symbol)
    if meta is None:
        raise ValueError(f"Symbol '{symbol}' not found in symbol pool")

    current = _current_prices.get(symbol, meta["base"])
    factor = (1 - magnitude_pct / 100) if direction == "down" else (1 + magnitude_pct / 100)
    shocked_price = round(current * factor, 2)
    _current_prices[symbol] = shocked_price

    await _publish_tick(symbol, shocked_price, meta["token"], "shock")
    logger.warning(
        "Shock applied",
        symbol=symbol,
        direction=direction,
        magnitude_pct=magnitude_pct,
        shocked_price=shocked_price,
    )
    return shocked_price


async def get_current_prices() -> dict[str, float]:
    """Return the latest in-memory mock prices for all symbols."""
    return dict(_current_prices)


# ---------------------------------------------------------------------------
# Standalone entry point
# ---------------------------------------------------------------------------

async def run_worker() -> None:
    """Entry point for running the mock poller as a standalone process."""
    from app.core.logger import setup_logging
    setup_logging()
    await connect_to_mongodb()
    try:
        await mock_price_poller_worker()
    finally:
        if _producer:
            await _producer.stop()
        await close_mongodb()


if __name__ == "__main__":
    asyncio.run(run_worker())

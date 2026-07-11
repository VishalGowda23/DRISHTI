"""
RiskLens AI — Kafka Consumer Factory
Provides a reusable AIOKafkaConsumer factory used by background workers.
Each worker creates its own consumer instance (not a singleton) so that
multiple workers can consume from different topics / groups independently.
"""

import json
from typing import Callable, Awaitable, Any
from aiokafka import AIOKafkaConsumer
from app.core.config import get_settings
from app.core.logger import get_logger

logger = get_logger("infrastructure.kafka.consumer")


def build_consumer(
    *topics: str,
    group_id: str | None = None,
    auto_offset_reset: str = "latest",
) -> AIOKafkaConsumer:
    """Create (but do not start) an AIOKafkaConsumer for the given topics.

    Args:
        *topics: One or more Kafka topic names to subscribe to.
        group_id: Consumer group ID. Defaults to settings.kafka_group_id.
        auto_offset_reset: ``"earliest"`` or ``"latest"``.

    Returns:
        A configured but not-yet-started AIOKafkaConsumer instance.

    Example::

        consumer = build_consumer("stock-price-updates", group_id="price-worker")
        await consumer.start()
        try:
            async for msg in consumer:
                await handle(msg)
        finally:
            await consumer.stop()
    """
    settings = get_settings()
    effective_group = group_id or settings.kafka_group_id

    return AIOKafkaConsumer(
        *topics,
        bootstrap_servers=settings.kafka_bootstrap_servers,
        group_id=effective_group,
        value_deserializer=lambda raw: json.loads(raw.decode("utf-8")),
        key_deserializer=lambda raw: raw.decode("utf-8") if raw else None,
        auto_offset_reset=auto_offset_reset,
        enable_auto_commit=True,
    )


async def consume_forever(
    *topics: str,
    group_id: str | None = None,
    handler: Callable[[Any], Awaitable[None]] = None,
    auto_offset_reset: str = "latest",
) -> None:
    """Start a consumer and process messages until cancelled.

    Args:
        *topics: Topic names to subscribe to.
        group_id: Consumer group ID.
        handler: Async callable invoked with each deserialized message value.
        auto_offset_reset: Offset reset policy.
    """
    consumer = build_consumer(*topics, group_id=group_id, auto_offset_reset=auto_offset_reset)
    await consumer.start()
    logger.info("Kafka consumer started", topics=list(topics), group_id=group_id)
    try:
        async for msg in consumer:
            try:
                if handler:
                    await handler(msg.value)
            except Exception as exc:
                logger.error(
                    "Message handler error",
                    topic=msg.topic,
                    offset=msg.offset,
                    error=str(exc),
                )
    finally:
        await consumer.stop()
        logger.info("Kafka consumer stopped")

"""
RiskLens AI — Kafka Producer
Publishes events to Kafka topics.
"""

import json
from typing import Optional
from aiokafka import AIOKafkaProducer
from app.core.config import get_settings
from app.core.logger import get_logger

logger = get_logger("infrastructure.kafka.producer")

_producer: Optional[AIOKafkaProducer] = None


async def get_kafka_producer() -> AIOKafkaProducer:
    """Get or create the Kafka producer singleton."""
    global _producer
    if _producer is None:
        settings = get_settings()
        _producer = AIOKafkaProducer(
            bootstrap_servers=settings.kafka_bootstrap_servers,
            value_serializer=lambda v: json.dumps(v, default=str).encode("utf-8"),
            key_serializer=lambda k: k.encode("utf-8") if k else None,
        )
        await _producer.start()
        logger.info("Kafka producer started")
    return _producer


async def publish_event(topic: str, key: str, value: dict) -> None:
    """Publish an event to a Kafka topic.

    Args:
        topic: Kafka topic name
        key: Message key (e.g., portfolio_id)
        value: Message payload dict
    """
    try:
        producer = await get_kafka_producer()
        await producer.send_and_wait(topic, value=value, key=key)
        logger.debug("Event published", topic=topic, key=key)
    except Exception as e:
        logger.error("Failed to publish Kafka event", topic=topic, error=str(e))


async def close_kafka_producer() -> None:
    """Gracefully close the Kafka producer."""
    global _producer
    if _producer:
        await _producer.stop()
        _producer = None
        logger.info("Kafka producer stopped")

"""
RiskLens AI — MongoDB Connection Manager
Async MongoDB client using Motor.
"""

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from app.core.config import get_settings
from app.core.logger import get_logger

logger = get_logger("infrastructure.mongodb")

_client: AsyncIOMotorClient | None = None
_db: AsyncIOMotorDatabase | None = None


async def connect_to_mongodb() -> None:
    """Initialize MongoDB connection."""
    global _client, _db
    settings = get_settings()

    logger.info("Connecting to MongoDB", uri=settings.mongodb_uri[:30] + "...")
    _client = AsyncIOMotorClient(settings.mongodb_uri)
    _db = _client[settings.mongodb_db_name]

    # Verify connection
    await _client.admin.command("ping")
    logger.info("MongoDB connected", database=settings.mongodb_db_name)


async def close_mongodb() -> None:
    """Close MongoDB connection."""
    global _client
    if _client:
        _client.close()
        logger.info("MongoDB connection closed")


def get_database() -> AsyncIOMotorDatabase:
    """Get the database instance. Must call connect_to_mongodb() first."""
    if _db is None:
        raise RuntimeError("MongoDB not connected. Call connect_to_mongodb() first.")
    return _db


def get_collection(name: str):
    """Get a specific collection from the database."""
    return get_database()[name]

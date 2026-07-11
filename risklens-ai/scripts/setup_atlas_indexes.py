#!/usr/bin/env python3
"""
RiskLens AI — MongoDB Atlas Index Setup Script
Creates all necessary collections and indexes in Atlas.
Run this once after connecting to Atlas for the first time.

Usage:
    python scripts/setup_atlas_indexes.py
"""

import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
from app.core.config import get_settings
from app.core.logger import get_logger

logger = get_logger("setup_atlas_indexes")


async def setup_indexes():
    """Create collections and indexes in Atlas MongoDB."""
    settings = get_settings()

    # Connect to MongoDB
    logger.info("Connecting to MongoDB Atlas...")
    client = AsyncIOMotorClient(settings.mongodb_uri)
    db = client[settings.mongodb_db_name]

    try:
        # Verify connection
        await client.admin.command("ping")
        logger.info(f"✅ Connected to {settings.mongodb_db_name}")

        # ---- Collections and Indexes ----
        collections_config = {
            "portfolios": [
                ({"status": 1}, {}),
                ({"fund_name": 1}, {}),
                ({"created_at": -1}, {}),
            ],
            "positions": [
                ({"portfolio_id": 1}, {}),
                ({"symbol": 1}, {}),
                ({"sector": 1}, {}),
                ({"country": 1}, {}),
                ({"portfolio_id": 1, "symbol": 1}, {"unique": True}),
            ],
            "risk_limits": [
                ({"portfolio_id": 1}, {"unique": True}),
            ],
            "assessments": [
                ({"portfolio_id": 1, "timestamp": -1}, {}),
                ({"claude_analysis.severity": 1}, {}),
                ({"status": 1}, {}),
            ],
            "alerts": [
                ({"portfolio_id": 1}, {}),
                ({"severity": 1}, {}),
                ({"status": 1}, {}),
                ({"created_at": -1}, {}),
            ],
            "audit_logs": [
                ({"timestamp": -1}, {}),
                ({"action": 1}, {}),
                ({"portfolio_id": 1}, {}),
            ],
            "market_data": [
                ({"symbol": 1, "timestamp": -1}, {}),
                ({"timestamp": -1}, {"expireAfterSeconds": 86400}),  # TTL: 24h
            ],
            "notifications": [
                ({"alert_id": 1}, {}),
                ({"status": 1}, {}),
                ({"created_at": -1}, {}),
            ],
        }

        for collection_name, indexes in collections_config.items():
            logger.info(f"Setting up collection: {collection_name}")

            # Create collection (idempotent in Atlas)
            try:
                await db.create_collection(collection_name)
                logger.info(f"  ✓ Created collection")
            except Exception as e:
                if "already exists" in str(e):
                    logger.info(f"  ℹ Collection already exists")
                else:
                    logger.warning(f"  ⚠ {e}")

            # Create indexes
            collection = db[collection_name]
            for index_keys, index_options in indexes:
                try:
                    await collection.create_index(list(index_keys.items()), **index_options)
                    logger.info(f"  ✓ Index created: {index_keys}")
                except Exception as e:
                    logger.warning(f"  ⚠ Index creation failed: {e}")

        logger.info("✅ Database setup complete!")

    finally:
        client.close()
        logger.info("Connection closed")


if __name__ == "__main__":
    asyncio.run(setup_indexes())

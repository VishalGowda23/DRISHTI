"""
RiskLens AI — Database Seed Script
Loads sample portfolios into MongoDB for demo purposes.
"""

import asyncio
import json
import os
import sys

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.infrastructure.database.mongodb import connect_to_mongodb, close_mongodb
from app.services.ingestion_service import IngestionService
from app.core.logger import setup_logging, get_logger

logger = get_logger("scripts.seed")

SAMPLE_DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "sample-data")


async def seed():
    """Load all sample portfolios into the database."""
    setup_logging()
    await connect_to_mongodb()

    logger.info("🌱 Seeding database with sample portfolios...")

    # Load JSON portfolios
    json_files = [
        ("portfolio_alpha_growth.json", "Alpha Growth Opportunities Fund", "Multi-Asset – Long Only"),
        ("portfolio_high_risk.json", "Concentrated Tech Fund", "Equity – Sector Specific"),
    ]

    for filename, fund_name, fund_type in json_files:
        filepath = os.path.join(SAMPLE_DATA_DIR, filename)
        if os.path.exists(filepath):
            try:
                with open(filepath, "r") as f:
                    data = json.load(f)
                portfolio_id, count = await IngestionService.ingest_from_json(
                    data=data, fund_name=fund_name, fund_type=fund_type,
                )
                logger.info(f"✅ Loaded {filename}", portfolio_id=portfolio_id, positions=count)
            except Exception as e:
                logger.error(f"❌ Failed to load {filename}", error=str(e))

    # Load CSV portfolios
    csv_files = [
        ("portfolio_balanced_income.csv", "Balanced Income Fund", "Multi-Asset – Balanced"),
    ]

    for filename, fund_name, fund_type in csv_files:
        filepath = os.path.join(SAMPLE_DATA_DIR, filename)
        if os.path.exists(filepath):
            try:
                with open(filepath, "rb") as f:
                    content = f.read()
                portfolio_id, count = await IngestionService.ingest_from_csv(
                    file_content=content, fund_name=fund_name, fund_type=fund_type,
                )
                logger.info(f"✅ Loaded {filename}", portfolio_id=portfolio_id, positions=count)
            except Exception as e:
                logger.error(f"❌ Failed to load {filename}", error=str(e))

    await close_mongodb()
    logger.info("🎉 Database seeding complete!")


if __name__ == "__main__":
    asyncio.run(seed())

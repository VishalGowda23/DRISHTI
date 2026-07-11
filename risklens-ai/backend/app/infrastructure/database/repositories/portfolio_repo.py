"""
RiskLens AI — Portfolio Repository
Data access layer for portfolios and positions.
"""

from typing import List, Optional, Dict, Any
from datetime import datetime
from app.infrastructure.database.mongodb import get_collection
from app.core.logger import get_logger

logger = get_logger("repo.portfolio")

PORTFOLIOS = "portfolios"
POSITIONS = "positions"


class PortfolioRepository:
    """Repository for portfolio CRUD operations."""

    @staticmethod
    async def create(portfolio: dict) -> str:
        """Insert a new portfolio."""
        collection = get_collection(PORTFOLIOS)
        result = await collection.insert_one(portfolio)
        logger.info("Portfolio created", portfolio_id=portfolio.get("_id"))
        return str(result.inserted_id)

    @staticmethod
    async def get_by_id(portfolio_id: str) -> Optional[dict]:
        """Get a portfolio by ID."""
        collection = get_collection(PORTFOLIOS)
        return await collection.find_one({"_id": portfolio_id})

    @staticmethod
    async def list_all(
        status: Optional[str] = None,
        page: int = 1,
        limit: int = 20,
    ) -> tuple[List[dict], int]:
        """List portfolios with optional filtering and pagination."""
        collection = get_collection(PORTFOLIOS)
        query: Dict[str, Any] = {}
        if status:
            query["status"] = status

        total = await collection.count_documents(query)
        cursor = collection.find(query).sort("created_at", -1).skip((page - 1) * limit).limit(limit)
        portfolios = await cursor.to_list(length=limit)
        return portfolios, total

    @staticmethod
    async def update(portfolio_id: str, update_data: dict) -> bool:
        """Update a portfolio."""
        collection = get_collection(PORTFOLIOS)
        update_data["updated_at"] = datetime.utcnow().isoformat()
        result = await collection.update_one(
            {"_id": portfolio_id},
            {"$set": update_data},
        )
        return result.modified_count > 0

    @staticmethod
    async def delete(portfolio_id: str) -> bool:
        """Delete a portfolio and its positions."""
        portfolios = get_collection(PORTFOLIOS)
        positions = get_collection(POSITIONS)
        await positions.delete_many({"portfolio_id": portfolio_id})
        result = await portfolios.delete_one({"_id": portfolio_id})
        return result.deleted_count > 0


class PositionRepository:
    """Repository for position CRUD operations."""

    @staticmethod
    async def bulk_insert(positions: List[dict]) -> int:
        """Insert multiple positions at once."""
        if not positions:
            return 0
        collection = get_collection(POSITIONS)
        result = await collection.insert_many(positions)
        logger.info("Positions inserted", count=len(result.inserted_ids))
        return len(result.inserted_ids)

    @staticmethod
    async def get_by_portfolio(portfolio_id: str) -> List[dict]:
        """Get all positions for a portfolio."""
        collection = get_collection(POSITIONS)
        cursor = collection.find({"portfolio_id": portfolio_id})
        return await cursor.to_list(length=1000)

    @staticmethod
    async def update_price(symbol: str, portfolio_id: str, price: float) -> bool:
        """Update current price for a position."""
        collection = get_collection(POSITIONS)
        result = await collection.update_one(
            {"symbol": symbol, "portfolio_id": portfolio_id},
            {"$set": {
                "current_price": price,
                "last_price_update": datetime.utcnow().isoformat(),
            }},
        )
        return result.modified_count > 0

    @staticmethod
    async def update_nav_percentages(portfolio_id: str, total_nav: float) -> None:
        """Recalculate market_value and nav_percentage for all positions."""
        collection = get_collection(POSITIONS)
        positions = await collection.find({"portfolio_id": portfolio_id}).to_list(length=1000)

        for pos in positions:
            market_value = pos.get("quantity", 0) * pos.get("current_price", 0)
            nav_pct = (market_value / total_nav * 100) if total_nav > 0 else 0
            await collection.update_one(
                {"_id": pos["_id"]},
                {"$set": {
                    "market_value": round(market_value, 2),
                    "nav_percentage": round(nav_pct, 2),
                }},
            )

    @staticmethod
    async def delete_by_portfolio(portfolio_id: str) -> int:
        """Delete all positions for a portfolio."""
        collection = get_collection(POSITIONS)
        result = await collection.delete_many({"portfolio_id": portfolio_id})
        return result.deleted_count

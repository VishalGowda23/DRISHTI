"""
RiskLens AI — Ingestion Service
Handles portfolio data upload, parsing, normalization, and validation.
"""

import csv
import io
import json
import uuid
from datetime import datetime
from typing import List, Dict, Any, Tuple
from app.core.logger import get_logger
from app.core.constants import VALID_ASSET_CLASSES, DEFAULT_RISK_LIMITS, DEFAULT_WARNING_BUFFER_PCT
from app.domain.enums import AssetClass, PortfolioStatus
from app.infrastructure.database.repositories.portfolio_repo import PortfolioRepository, PositionRepository
from app.infrastructure.database.repositories.assessment_repo import ConfigRepository

logger = get_logger("services.ingestion")

# Required CSV columns
REQUIRED_CSV_COLUMNS = {"symbol", "name", "asset_class", "sector", "country", "quantity"}
OPTIONAL_CSV_COLUMNS = {"current_price", "avg_cost_price", "currency", "isin", "exchange"}


class IngestionService:
    """Handles portfolio data ingestion from CSV and JSON formats."""

    @staticmethod
    async def ingest_from_json(
        data: Dict[str, Any],
        fund_name: str,
        fund_type: str = "Multi-Asset",
    ) -> Tuple[str, int]:
        """Ingest portfolio from JSON payload.

        Expected format:
        {
            "fund_name": "...",
            "fund_type": "...",
            "positions": [
                {"symbol": "RELIANCE.NS", "name": "Reliance Industries", ...}
            ]
        }

        Args:
            data: JSON dict with portfolio data
            fund_name: Fund name
            fund_type: Fund type

        Returns:
            Tuple of (portfolio_id, positions_count)
        """
        positions_data = data.get("positions", [])
        if not positions_data:
            raise ValueError("No positions found in JSON data")

        return await IngestionService._process_positions(
            positions_data=positions_data,
            fund_name=fund_name,
            fund_type=fund_type,
            manager=data.get("manager"),
            currency=data.get("currency", "INR"),
        )

    @staticmethod
    async def ingest_from_csv(
        file_content: bytes,
        fund_name: str,
        fund_type: str = "Multi-Asset",
    ) -> Tuple[str, int]:
        """Ingest portfolio from CSV file content.

        Args:
            file_content: Raw bytes of CSV file
            fund_name: Fund name
            fund_type: Fund type

        Returns:
            Tuple of (portfolio_id, positions_count)
        """
        try:
            text = file_content.decode("utf-8")
        except UnicodeDecodeError:
            text = file_content.decode("latin-1")

        reader = csv.DictReader(io.StringIO(text))
        columns = set(reader.fieldnames or [])

        # Validate required columns
        missing = REQUIRED_CSV_COLUMNS - columns
        if missing:
            raise ValueError(f"Missing required columns: {', '.join(missing)}")

        positions_data = []
        for row in reader:
            positions_data.append({
                "symbol": row.get("symbol", "").strip(),
                "name": row.get("name", "").strip(),
                "asset_class": row.get("asset_class", "equity").strip().lower(),
                "sector": row.get("sector", "Unknown").strip(),
                "country": row.get("country", "Unknown").strip(),
                "quantity": float(row.get("quantity", 0)),
                "current_price": float(row.get("current_price", 0)) if row.get("current_price") else 0,
                "avg_cost_price": float(row.get("avg_cost_price", 0)) if row.get("avg_cost_price") else 0,
                "currency": row.get("currency", "INR").strip(),
            })

        if not positions_data:
            raise ValueError("CSV file contains no valid position rows")

        return await IngestionService._process_positions(
            positions_data=positions_data,
            fund_name=fund_name,
            fund_type=fund_type,
        )

    @staticmethod
    async def _process_positions(
        positions_data: List[dict],
        fund_name: str,
        fund_type: str,
        manager: str = None,
        currency: str = "INR",
    ) -> Tuple[str, int]:
        """Normalize and store portfolio + positions.

        Args:
            positions_data: List of raw position dicts
            fund_name: Fund name
            fund_type: Fund type

        Returns:
            Tuple of (portfolio_id, positions_count)
        """
        portfolio_id = f"PORT-{datetime.utcnow().strftime('%Y')}-{uuid.uuid4().hex[:4].upper()}"

        # Calculate initial values
        total_nav = 0
        normalized_positions = []

        for i, pos in enumerate(positions_data):
            # Validate asset class
            asset_class = pos.get("asset_class", "equity")
            if asset_class not in VALID_ASSET_CLASSES:
                asset_class = "equity"

            quantity = float(pos.get("quantity", 0))
            price = float(pos.get("current_price", 0))
            market_value = quantity * price

            position = {
                "_id": f"POS-{portfolio_id}-{i:03d}",
                "portfolio_id": portfolio_id,
                "symbol": pos.get("symbol", f"UNKNOWN-{i}"),
                "name": pos.get("name", f"Unknown Position {i}"),
                "asset_class": asset_class,
                "sector": pos.get("sector", "Unknown"),
                "country": pos.get("country", "Unknown"),
                "quantity": quantity,
                "avg_cost_price": float(pos.get("avg_cost_price", price)),
                "current_price": price,
                "market_value": round(market_value, 2),
                "nav_percentage": 0,  # Calculated after total NAV
                "currency": pos.get("currency", currency),
                "last_price_update": datetime.utcnow().isoformat(),
                "metadata": {
                    "isin": pos.get("isin", ""),
                    "exchange": pos.get("exchange", ""),
                    "lot_size": int(pos.get("lot_size", 1)),
                },
            }
            normalized_positions.append(position)
            total_nav += market_value

        # Calculate NAV percentages
        for pos in normalized_positions:
            if total_nav > 0:
                pos["nav_percentage"] = round((pos["market_value"] / total_nav) * 100, 2)

        # Create portfolio document
        portfolio = {
            "_id": portfolio_id,
            "fund_name": fund_name,
            "fund_type": fund_type,
            "manager": manager,
            "currency": currency,
            "status": PortfolioStatus.ACTIVE.value,
            "total_nav": round(total_nav, 2),
            "positions_count": len(normalized_positions),
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat(),
            "metadata": {},
        }

        # Store in database
        await PortfolioRepository.create(portfolio)
        await PositionRepository.bulk_insert(normalized_positions)

        # Create default risk limits for this portfolio
        default_config = {
            "_id": f"RL-{portfolio_id}",
            "portfolio_id": portfolio_id,
            "limits": DEFAULT_RISK_LIMITS,
            "warning_buffer_pct": DEFAULT_WARNING_BUFFER_PCT,
            "is_default": True,
            "created_at": datetime.utcnow().isoformat(),
            "updated_by": "system",
        }
        await ConfigRepository.upsert_limits(portfolio_id, default_config)

        logger.info(
            "Portfolio ingested successfully",
            portfolio_id=portfolio_id,
            positions=len(normalized_positions),
            total_nav=total_nav,
        )

        return portfolio_id, len(normalized_positions)

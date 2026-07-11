"""
RiskLens AI — Market Data Worker
Background worker that polls Yahoo Finance every 60 seconds
and publishes price updates to Kafka.
"""

import asyncio
from datetime import datetime
from app.core.config import get_settings
from app.core.logger import get_logger
from app.core.constants import TOPIC_MARKET_PRICES, TOPIC_PORTFOLIO_EVENTS
from app.infrastructure.external.yahoo_finance import get_yahoo_client
from app.infrastructure.database.repositories.portfolio_repo import PortfolioRepository, PositionRepository
from app.infrastructure.database.mongodb import connect_to_mongodb, close_mongodb
from app.services.risk_analysis_service import RiskAnalysisService
from app.domain.enums import AssessmentTrigger

logger = get_logger("workers.market_data")


async def market_data_worker():
    """Background worker that continuously polls Yahoo Finance for price updates.

    Flow:
    1. Fetch all active portfolios
    2. Collect unique symbols across all portfolios
    3. Fetch current prices from Yahoo Finance
    4. Update positions with new prices
    5. Trigger risk re-analysis for portfolios with significant price changes
    """
    settings = get_settings()
    interval = settings.yahoo_finance_poll_interval_seconds
    yahoo = get_yahoo_client()

    logger.info("Market data worker started", interval_seconds=interval)

    while True:
        try:
            # Get all active portfolios
            portfolios, _ = await PortfolioRepository.list_all(status="active", limit=100)

            if not portfolios:
                logger.debug("No active portfolios found")
                await asyncio.sleep(interval)
                continue

            # Collect all unique symbols
            all_symbols = set()
            portfolio_symbols = {}

            for portfolio in portfolios:
                pid = portfolio["_id"]
                positions = await PositionRepository.get_by_portfolio(pid)
                symbols = [
                    p["symbol"] for p in positions
                    if p.get("symbol") and p.get("asset_class") != "cash"
                ]
                portfolio_symbols[pid] = symbols
                all_symbols.update(symbols)

            if not all_symbols:
                await asyncio.sleep(interval)
                continue

            # Fetch prices
            logger.info("Fetching market prices", symbol_count=len(all_symbols))
            prices = yahoo.get_current_prices(list(all_symbols))

            # Update positions and check for significant changes
            for portfolio in portfolios:
                pid = portfolio["_id"]
                symbols = portfolio_symbols.get(pid, [])
                significant_change = False

                for symbol in symbols:
                    if symbol in prices and prices[symbol]["price"] > 0:
                        old_price = 0
                        positions = await PositionRepository.get_by_portfolio(pid)
                        for pos in positions:
                            if pos.get("symbol") == symbol:
                                old_price = pos.get("current_price", 0)
                                break

                        new_price = prices[symbol]["price"]
                        await PositionRepository.update_price(symbol, pid, new_price)

                        # Check for significant price change (> 2%)
                        if old_price > 0:
                            change_pct = abs((new_price - old_price) / old_price) * 100
                            if change_pct > 2.0:
                                significant_change = True

                # Re-analyze if significant price changes detected
                if significant_change:
                    logger.info("Significant price change detected, triggering re-analysis", portfolio_id=pid)
                    try:
                        await RiskAnalysisService.analyze_portfolio(
                            portfolio_id=pid,
                            trigger=AssessmentTrigger.PRICE_CHANGE,
                        )
                    except Exception as e:
                        logger.error("Re-analysis failed", portfolio_id=pid, error=str(e))

            logger.info("Market data update complete", portfolios_updated=len(portfolios))

        except Exception as e:
            logger.error("Market data worker error", error=str(e))

        await asyncio.sleep(interval)


async def run_worker():
    """Entry point for the market data worker."""
    from app.core.logger import setup_logging
    setup_logging()
    await connect_to_mongodb()
    try:
        await market_data_worker()
    finally:
        await close_mongodb()


if __name__ == "__main__":
    asyncio.run(run_worker())

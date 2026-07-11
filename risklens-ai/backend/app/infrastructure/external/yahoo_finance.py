"""
RiskLens AI — Yahoo Finance Client
Fetches real-time stock prices and historical data for volatility calculation.
"""

import yfinance as yf
from typing import Dict, List, Optional
from datetime import datetime, timedelta
import pybreaker
from app.core.logger import get_logger

logger = get_logger("infrastructure.yahoo_finance")

# Circuit breaker: Trip after 3 failures, reset after 60 seconds
yahoo_breaker = pybreaker.CircuitBreaker(fail_max=3, reset_timeout=60)

class YahooFinanceClient:
    """Client for fetching market data from Yahoo Finance with Circuit Breaker."""

    @staticmethod
    @yahoo_breaker
    def _fetch_prices_internal(symbols: List[str]) -> Dict[str, dict]:
        results = {}
        tickers = yf.Tickers(" ".join(symbols))
        for symbol in symbols:
            try:
                ticker = tickers.tickers.get(symbol)
                if ticker is None:
                    continue
                info = ticker.fast_info
                results[symbol] = {
                    "price": round(float(info.get("lastPrice", 0) or info.get("last_price", 0)), 2),
                    "previous_close": round(float(info.get("previousClose", 0) or info.get("previous_close", 0)), 2),
                    "day_change_pct": round(float(info.get("lastPrice", 0) - info.get("previousClose", 0)) / max(info.get("previousClose", 1), 1) * 100, 2) if info.get("previousClose") else 0,
                    "volume": int(info.get("lastVolume", 0) or info.get("last_volume", 0)),
                }
            except Exception as e:
                logger.warning(f"Failed to get price for {symbol}", error=str(e))
                results[symbol] = {"price": 0, "previous_close": 0, "day_change_pct": 0, "volume": 0}
        return results

    @staticmethod
    def get_current_prices(symbols: List[str]) -> Dict[str, dict]:
        """Get current prices for a list of symbols with fallback mock data."""
        try:
            return YahooFinanceClient._fetch_prices_internal(symbols)
        except pybreaker.CircuitBreakerError:
            logger.error("Yahoo Finance Circuit Breaker OPEN! Using mock price data.")
            return {sym: {"price": 100.0, "previous_close": 98.0, "day_change_pct": 2.04, "volume": 1000000} for sym in symbols}
        except Exception as e:
            logger.error("Yahoo Finance batch fetch failed", error=str(e))
            return {sym: {"price": 100.0, "previous_close": 98.0, "day_change_pct": 2.04, "volume": 1000000} for sym in symbols}

    @staticmethod
    @yahoo_breaker
    def _fetch_historical_returns_internal(symbols: List[str], days: int) -> Dict[str, List[float]]:
        results = {}
        end_date = datetime.now()
        start_date = end_date - timedelta(days=int(days * 1.5))
        for symbol in symbols:
            try:
                ticker = yf.Ticker(symbol)
                hist = ticker.history(start=start_date, end=end_date)
                if hist.empty or len(hist) < 5:
                    logger.warning(f"Insufficient history for {symbol}", rows=len(hist))
                    continue
                closes = hist["Close"].tolist()
                returns = []
                for i in range(1, min(len(closes), days + 1)):
                    daily_return = (closes[i] - closes[i - 1]) / closes[i - 1]
                    returns.append(round(daily_return, 6))
                results[symbol] = returns
            except Exception as e:
                logger.warning(f"Failed to get history for {symbol}", error=str(e))
        return results

    @staticmethod
    def get_historical_returns(symbols: List[str], days: int = 30) -> Dict[str, List[float]]:
        """Get historical daily returns with fallback mock data."""
        try:
            return YahooFinanceClient._fetch_historical_returns_internal(symbols, days)
        except pybreaker.CircuitBreakerError:
            logger.error("Yahoo Finance Circuit Breaker OPEN! Using mock historical returns.")
            return {sym: [0.01, -0.005, 0.02, -0.01, 0.005] * (days // 5 + 1) for sym in symbols}
        except Exception as e:
            logger.error("Yahoo Finance historical batch fetch failed", error=str(e))
            return {sym: [0.01, -0.005, 0.02, -0.01, 0.005] * (days // 5 + 1) for sym in symbols}

    @staticmethod
    @yahoo_breaker
    def _fetch_volatility_internal(symbol: str, current_days: int, previous_days: int) -> dict:
        import numpy as np
        ticker = yf.Ticker(symbol)
        hist = ticker.history(period=f"{previous_days + 30}d")
        if hist.empty or len(hist) < current_days:
            return {"volatility_30d": 0, "volatility_prev_quarter": 0, "change_pct": 0}
        closes = hist["Close"].values
        returns = np.diff(closes) / closes[:-1]
        current_vol = float(np.std(returns[-current_days:]) * np.sqrt(252))
        prev_returns = returns[:-current_days]
        prev_vol = float(np.std(prev_returns[-current_days:]) * np.sqrt(252)) if len(prev_returns) >= current_days else current_vol
        change_pct = ((current_vol - prev_vol) / prev_vol * 100) if prev_vol > 0 else 0
        return {
            "volatility_30d": round(current_vol, 4),
            "volatility_prev_quarter": round(prev_vol, 4),
            "change_pct": round(change_pct, 2),
        }

    @staticmethod
    def get_volatility(symbol: str, current_days: int = 30, previous_days: int = 90) -> dict:
        """Calculate 30-day realized volatility with fallback mock data."""
        try:
            return YahooFinanceClient._fetch_volatility_internal(symbol, current_days, previous_days)
        except pybreaker.CircuitBreakerError:
            logger.error("Yahoo Finance Circuit Breaker OPEN! Using mock volatility.")
            return {"volatility_30d": 0.15, "volatility_prev_quarter": 0.12, "change_pct": 25.0}
        except Exception as e:
            logger.warning(f"Volatility calculation failed for {symbol}", error=str(e))
            return {"volatility_30d": 0.15, "volatility_prev_quarter": 0.12, "change_pct": 25.0}


# Singleton
_yahoo_client: Optional[YahooFinanceClient] = None


def get_yahoo_client() -> YahooFinanceClient:
    global _yahoo_client
    if _yahoo_client is None:
        _yahoo_client = YahooFinanceClient()
    return _yahoo_client

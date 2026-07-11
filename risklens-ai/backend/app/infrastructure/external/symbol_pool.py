"""
RiskLens AI — NSE Symbol Pool
Static registry of the 18 NSE equity symbols used for synthetic data generation.
Each entry contains the symbol name, Zerodha instrument token, and a base price
used as the starting point when no real market data is available.

Usage:
    from app.infrastructure.external.symbol_pool import SYMBOL_POOL, get_symbol_meta, symbol_base_prices

The Yahoo Finance ticker for each symbol is ``{symbol}.NS``.
"""

from typing import Optional

# ---------------------------------------------------------------------------
# Static symbol registry
# ---------------------------------------------------------------------------

SYMBOL_POOL: list[dict] = [
    {"symbol": "RELIANCE",   "token": 738561,   "base": 2450.0,  "sector": "Energy",          "country": "India"},
    {"symbol": "TCS",        "token": 2953217,  "base": 3850.0,  "sector": "IT",              "country": "India"},
    {"symbol": "INFY",       "token": 408065,   "base": 1520.0,  "sector": "IT",              "country": "India"},
    {"symbol": "HDFCBANK",   "token": 341249,   "base": 1680.0,  "sector": "Banking",         "country": "India"},
    {"symbol": "ICICIBANK",  "token": 1270529,  "base": 1015.0,  "sector": "Banking",         "country": "India"},
    {"symbol": "HINDUNILVR", "token": 356865,   "base": 2580.0,  "sector": "FMCG",            "country": "India"},
    {"symbol": "ITC",        "token": 424961,   "base": 422.0,   "sector": "FMCG",            "country": "India"},
    {"symbol": "SBIN",       "token": 779521,   "base": 555.0,   "sector": "Banking",         "country": "India"},
    {"symbol": "BHARTIARTL", "token": 2714625,  "base": 1285.0,  "sector": "Telecom",         "country": "India"},
    {"symbol": "KOTAKBANK",  "token": 492033,   "base": 1885.0,  "sector": "Banking",         "country": "India"},
    {"symbol": "LT",         "token": 2939649,  "base": 3185.0,  "sector": "Infrastructure",  "country": "India"},
    {"symbol": "AXISBANK",   "token": 1510401,  "base": 1095.0,  "sector": "Banking",         "country": "India"},
    {"symbol": "MARUTI",     "token": 2815745,  "base": 9825.0,  "sector": "Auto",            "country": "India"},
    {"symbol": "SUNPHARMA",  "token": 857857,   "base": 685.0,   "sector": "Pharma",          "country": "India"},
    {"symbol": "TATAMOTORS", "token": 884737,   "base": 1725.0,  "sector": "Auto",            "country": "India"},
    {"symbol": "WIPRO",      "token": 969473,   "base": 520.0,   "sector": "IT",              "country": "India"},
    {"symbol": "ASIANPAINT", "token": 60417,    "base": 2985.0,  "sector": "Consumer",        "country": "India"},
    {"symbol": "TITAN",      "token": 897537,   "base": 3255.0,  "sector": "Consumer",        "country": "India"},
]

# ---------------------------------------------------------------------------
# Convenience helpers
# ---------------------------------------------------------------------------

def get_symbol_meta(symbol: str) -> Optional[dict]:
    """Return the full metadata dict for a symbol, or None if not found."""
    return next((s for s in SYMBOL_POOL if s["symbol"] == symbol), None)


def symbol_base_prices() -> dict[str, float]:
    """Return a ``{symbol: base_price}`` dict for all symbols in the pool."""
    return {s["symbol"]: s["base"] for s in SYMBOL_POOL}


def yahoo_ticker(symbol: str) -> str:
    """Convert a bare NSE symbol to its Yahoo Finance ticker (e.g. RELIANCE → RELIANCE.NS)."""
    return f"{symbol}.NS"

"""
RiskLens AI — AI Prompt Validation Script
Loads a sample portfolio, runs the rule engine, and invokes Claude.
"""

import sys
import json
import asyncio
from pathlib import Path

# Add backend to path so we can import app modules
sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

from app.domain.models.audit import RiskLimits
from app.domain.rules.concentration_rules import run_all_concentration_checks
from app.infrastructure.ai.claude_client import get_claude_client
from app.core.config import get_settings

async def main():
    # Make sure we have an API key set
    settings = get_settings()
    if not settings.anthropic_api_key:
        print("WARNING: ANTHROPIC_API_KEY is not set. The client will fall back or fail.")
        
    sample_file = Path(__file__).parent.parent / "sample-data" / "portfolio_alpha_growth.json"
    
    print(f"Loading {sample_file}...")
    try:
        with open(sample_file, "r") as f:
            data = json.load(f)
    except FileNotFoundError:
        print(f"Could not find {sample_file}. Please run from project root.")
        return
        
    portfolio_context = {
        "portfolio_id": data.get("id", "alpha_growth_1"),
        "fund_name": data.get("name", "Alpha Growth Fund"),
        "fund_type": data.get("type", "Equity"),
        "total_nav": data.get("total_nav", 1000000.0),
        "currency": data.get("currency", "USD"),
        "position_count": len(data.get("positions", [])),
        "timestamp": data.get("timestamp", "2026-07-11T00:00:00Z"),
    }
    
    positions = data.get("positions", [])
    
    # Define some limits
    limits = RiskLimits(
        single_issuer_max=5.0,
        sector_max=20.0,
        geography_max=25.0,
        asset_class_max=100.0,
    )
    
    print("Running Rule Engine...")
    results = run_all_concentration_checks(
        positions=positions,
        total_nav=portfolio_context["total_nav"],
        limits=limits,
        warning_buffer=1.0,
    )
    
    print(f"Found {results.total_breaches} breaches and {results.total_warnings} warnings.")
    
    print("Invoking Claude...")
    client = get_claude_client()
    
    analysis, model_info = await client.analyze_portfolio_risk(
        portfolio_context=portfolio_context,
        rule_engine_results=results.model_dump(),
        top_positions=positions[:15],
        market_context={"volatility": "VIX at 22, market trending downwards"},
    )
    
    print("\n=== CLAUDE ANALYSIS ===")
    print(analysis.model_dump_json(indent=2))
    
    print("\n=== MODEL INFO ===")
    print(model_info.model_dump_json(indent=2))

if __name__ == "__main__":
    asyncio.run(main())

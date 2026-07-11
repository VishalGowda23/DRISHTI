"""
RiskLens AI — Demo Market Crash Simulation Script
Simulates a black swan tech crash event by generating a hyper-concentrated 
portfolio and running the Rule Engine -> Claude AI rebalancing pipeline.
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
from app.infrastructure.external.yahoo_finance import get_yahoo_client
from app.core.config import get_settings

async def main():
    print("==================================================================")
    print("💥 RiskLens AI - Black Swan Tech Crash Demo Simulation 💥")
    print("==================================================================")

    # 1. Setup concentrated Tech Portfolio
    fund_name = "Hyper-Concentrated Tech Growth Fund"
    total_nav = 10000000.0  # $10 Million
    currency = "USD"

    # Apple (AAPL) representing 55% of the portfolio (extreme breach)
    # Tesla (TSLA) representing 25% of the portfolio (extreme warning/breach)
    # Remaining 20% in other tech assets and cash
    positions = [
        {
            "symbol": "AAPL",
            "name": "Apple Inc.",
            "asset_class": "equity",
            "sector": "Technology",
            "country": "USA",
            "quantity": 25000,
            "current_price": 220.00,
            "market_value": 5500000.0,
            "nav_percentage": 55.0
        },
        {
            "symbol": "TSLA",
            "name": "Tesla Inc.",
            "asset_class": "equity",
            "sector": "Consumer Cyclical",
            "country": "USA",
            "quantity": 10000,
            "current_price": 250.00,
            "market_value": 2500000.0,
            "nav_percentage": 25.0
        },
        {
            "symbol": "NVDA",
            "name": "NVIDIA Corporation",
            "asset_class": "equity",
            "sector": "Technology",
            "country": "USA",
            "quantity": 7142,
            "current_price": 140.00,
            "market_value": 1000000.0,
            "nav_percentage": 10.0
        },
        {
            "symbol": "CASH_USD",
            "name": "USD Cash Account",
            "asset_class": "cash",
            "sector": "Cash",
            "country": "USA",
            "quantity": 1000000,
            "current_price": 1.0,
            "market_value": 1000000.0,
            "nav_percentage": 10.0
        }
    ]

    portfolio_context = {
        "portfolio_id": "demo_crash_portfolio_1",
        "fund_name": fund_name,
        "fund_type": "Equity - Aggressive Growth",
        "total_nav": total_nav,
        "currency": currency,
        "position_count": len(positions),
        "timestamp": "2026-07-11T12:00:00Z"
    }

    # Strict limits
    limits = RiskLimits(
        single_issuer_max=10.0,  # Max 10% per stock
        sector_max=30.0,         # Max 30% per sector
        geography_max=80.0,
        asset_class_max=100.0
    )

    print("\n🔍 Step 1: Pre-computing Concentration Checks using Rule Engine...")
    results = run_all_concentration_checks(
        positions=positions,
        total_nav=total_nav,
        limits=limits,
        warning_buffer=2.0
    )
    print(f"✅ Rule Engine execution complete. Found {results.total_breaches} breaches and {results.total_warnings} warnings.")
    
    # 2. Fetching real market context using Yahoo Finance client
    print("\n📈 Step 2: Fetching live Volatility Data via Yahoo Finance Client...")
    yahoo = get_yahoo_client()
    market_context = {}
    for pos in positions:
        sym = pos["symbol"]
        if sym != "CASH_USD":
            vol = yahoo.get_volatility(sym)
            if vol["volatility_30d"] > 0:
                market_context[sym] = vol
                print(f"   - {sym} 30-Day Volatility: {vol['volatility_30d']*100:.2f}% (Change vs Prev Quarter: {vol['change_pct']}%)")

    # 3. Invoking Claude
    print("\n🤖 Step 3: Triggering Claude AI for qualitative risk assessment & rebalancing trades...")
    client = get_claude_client()
    
    analysis, model_info = await client.analyze_portfolio_risk(
        portfolio_context=portfolio_context,
        rule_engine_results=results.model_dump(),
        top_positions=positions,
        market_context=market_context
    )

    print("\n========================= ASSESSMENT RESULTS =========================")
    print(f"Overall Risk Verdict: {analysis.overall_verdict}")
    print(f"Assessed Severity:   {analysis.severity.value}")
    print(f"AI Confidence Score: {analysis.confidence:.2f}")
    print(f"AI Rationale:        {analysis.rationale}")
    
    print("\n🚨 Breach Analysis:")
    for ba in analysis.breach_analysis:
        print(f"   - [{ba.risk_level.value}] {ba.entity} ({ba.type}): {ba.assessment}")
        
    print("\n💡 AI Proposed Agentic Rebalancing Trades:")
    if analysis.proposed_trades:
        for i, trade in enumerate(analysis.proposed_trades, 1):
            print(f"   {i}. {trade.action} {trade.amount_pct}% of NAV in {trade.symbol}")
            print(f"      Rationale: {trade.rationale}")
    else:
        print("   No proposed trades generated.")

    print("\n💼 Recommended Non-Trade Actions:")
    for action in analysis.recommended_actions:
        print(f"   - {action}")

    print("\n=========================== METRIC REPORT ===========================")
    print(f"Claude Model:         {model_info.model or get_settings().claude_model}")
    print(f"Prompt Tokens:        {model_info.prompt_tokens}")
    print(f"Completion Tokens:    {model_info.completion_tokens}")
    print(f"Estimated Review Time: {analysis.estimated_review_time_minutes} minutes")
    print("==================================================================")

if __name__ == "__main__":
    asyncio.run(main())

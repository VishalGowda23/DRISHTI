"""
RiskLens AI — Prompt Templates
All Claude prompt templates centralized here for version control and easy iteration.
"""

import json
from typing import Dict, Any


import os
from pathlib import Path

PROMPTS_DIR = Path(__file__).parent.parent.parent.parent.parent / "prompts"

def get_system_prompt() -> str:
    """System prompt that defines Claude's role and output format."""
    prompt_path = PROMPTS_DIR / "severity_scoring.md"
    try:
        with open(prompt_path, "r") as f:
            return f.read()
    except FileNotFoundError:
        # Fallback if running from a weird directory
        return "You are a senior portfolio risk analyst. Output valid JSON."


def build_concentration_analysis_prompt(
    portfolio_context: Dict[str, Any],
    rule_engine_results: Dict[str, Any],
    market_context: Dict[str, Any],
) -> str:
    """Build the user prompt for concentration analysis.

    Token optimization: Only include breaches, warnings, and flagged items.
    OK-status checks are summarized as counts, not sent in full.
    """
    # Filter to only non-OK results to save tokens
    filtered_results = _filter_significant_results(rule_engine_results)

    prompt_path = PROMPTS_DIR / "concentration_analysis.md"
    try:
        with open(prompt_path, "r") as f:
            template = f.read()
    except FileNotFoundError:
        template = "{rule_engine_results}"
        
    prompt = template.format(
        portfolio_id=portfolio_context.get('portfolio_id', 'N/A'),
        fund_name=portfolio_context.get('fund_name', 'N/A'),
        fund_type=portfolio_context.get('fund_type', 'N/A'),
        total_nav=f"{portfolio_context.get('total_nav', 0):,.2f}",
        currency=portfolio_context.get('currency', 'INR'),
        position_count=portfolio_context.get('position_count', 0),
        timestamp=portfolio_context.get('timestamp', 'N/A'),
        rule_engine_results=json.dumps(filtered_results, indent=2, default=str),
        market_context=json.dumps(market_context, indent=2, default=str) if market_context else "No market context available."
    )

    return prompt


def _filter_significant_results(rule_engine_results: Dict[str, Any]) -> Dict[str, Any]:
    """Filter rule engine results to only include breaches, warnings, and flags.

    This reduces token usage by ~40% by not sending OK-status items to Claude.
    """
    filtered = {}

    for check_type in ["issuer_checks", "sector_checks", "geography_checks", "asset_class_checks"]:
        checks = rule_engine_results.get(check_type, [])
        significant = [c for c in checks if c.get("status") in ("BREACH", "WARNING")]
        ok_count = len(checks) - len(significant)

        if significant:
            filtered[check_type] = significant
        if ok_count > 0:
            filtered[f"{check_type}_ok_count"] = ok_count

    # Always include correlation clusters
    clusters = rule_engine_results.get("correlation_clusters", [])
    if clusters:
        filtered["correlation_clusters"] = clusters

    filtered["summary"] = {
        "total_breaches": rule_engine_results.get("total_breaches", 0),
        "total_warnings": rule_engine_results.get("total_warnings", 0),
    }

    return filtered


def build_xai_report_prompt(
    assessment: Dict[str, Any],
    portfolio: Dict[str, Any],
) -> str:
    """Build prompt for generating an explainable AI report."""
    return f"""Generate a detailed Explainable AI (XAI) report for the following risk assessment.
The report should be written for a compliance officer who needs to understand:
1. What data was analyzed
2. What the AI concluded
3. Why the AI reached that conclusion (reasoning transparency)
4. What confidence level the AI assigned and why
5. What limitations exist in the analysis

### Assessment Data
{json.dumps(assessment, indent=2, default=str)}

### Portfolio Data
{json.dumps(portfolio, indent=2, default=str)}

Output a structured markdown report."""

"""
RiskLens AI — Prompt Templates
All Claude prompt templates centralized here for version control and easy iteration.
"""

import json
from typing import Dict, Any


def get_system_prompt() -> str:
    """System prompt that defines Claude's role and output format."""
    return """You are a senior portfolio risk analyst at a top-tier asset management firm with 15+ years of experience in risk management, concentration analysis, and regulatory compliance.

Your role is to analyze pre-computed portfolio concentration data and produce structured risk assessments for portfolio managers and risk desks.

CRITICAL RULES:
1. You are given pre-computed numbers from a rule engine. DO NOT recalculate percentages.
2. Your job is to INTERPRET the data, EXPLAIN the risk, and RECOMMEND actions.
3. Always consider the interaction between multiple breaches/warnings — compound risk is worse than isolated risk.
4. Factor in volatility context when available — rising volatility amplifies concentration risk.
5. Be specific in recommendations — "reduce Reliance by 1.8% NAV" is better than "reduce exposure".
6. Your confidence score should reflect uncertainty: 0.9+ for clear breaches, 0.5-0.7 for ambiguous signals.

Your output MUST be valid JSON matching the schema provided. No markdown, no explanation outside the JSON."""


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

    prompt = f"""### Portfolio Context
- Portfolio ID: {portfolio_context.get('portfolio_id', 'N/A')}
- Fund Name: {portfolio_context.get('fund_name', 'N/A')}
- Fund Type: {portfolio_context.get('fund_type', 'N/A')}
- Total NAV: {portfolio_context.get('total_nav', 0):,.2f}
- Currency: {portfolio_context.get('currency', 'INR')}
- Number of Positions: {portfolio_context.get('position_count', 0)}
- Assessment Timestamp: {portfolio_context.get('timestamp', 'N/A')}

### Concentration Analysis Results (Pre-Computed by Rule Engine)
{json.dumps(filtered_results, indent=2, default=str)}

### Market Context
{json.dumps(market_context, indent=2, default=str) if market_context else "No market context available."}

### Instructions
Analyze the above concentration data and produce a risk assessment. Focus on:
1. The severity of each breach — is it marginal (just over limit) or critical (significantly over)?
2. The interaction between multiple breaches/warnings — do they compound the risk?
3. Volatility trends that amplify or mitigate concentration risk
4. Correlation clusters that represent hidden, undiversified concentration
5. Specific, actionable rebalancing recommendations with estimated NAV impact

### Required Output (valid JSON only, no markdown wrapping):
{{
  "severity": "LOW | MEDIUM | HIGH | CRITICAL",
  "confidence": <float 0.0-1.0>,
  "rationale": "<2-3 sentence executive summary>",
  "breach_analysis": [
    {{
      "type": "issuer_concentration | sector_concentration | geography_concentration | correlation_cluster",
      "entity": "<name>",
      "assessment": "<detailed 1-2 sentence explanation>",
      "risk_level": "LOW | MEDIUM | HIGH | CRITICAL"
    }}
  ],
  "volatility_context": "<assessment of relevant volatility signals>",
  "historical_pattern": "<any relevant historical pattern observation>",
  "recommended_actions": ["<specific action 1>", "<specific action 2>"],
  "estimated_review_time_minutes": <int>,
  "overall_verdict": "<one-line summary for dashboard display>"
}}"""

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

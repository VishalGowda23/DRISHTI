### Portfolio Context
- Portfolio ID: {portfolio_id}
- Fund Name: {fund_name}
- Fund Type: {fund_type}
- Total NAV: {total_nav}
- Currency: {currency}
- Number of Positions: {position_count}
- Assessment Timestamp: {timestamp}

### Concentration Analysis Results (Pre-Computed by Rule Engine)
{rule_engine_results}

### Top Portfolio Positions
{top_positions}

### Market Context
{market_context}

### Instructions
Analyze the above concentration data and produce a risk assessment. Focus on:
1. The severity of each breach — is it marginal (just over limit) or critical (significantly over)?
2. The interaction between multiple breaches/warnings — do they compound the risk?
3. Volatility trends that amplify or mitigate concentration risk
4. Correlation clusters that represent hidden, undiversified concentration
5. Specific, actionable rebalancing recommendations, including proposing precise trades (`BUY` or `SELL` with target percentage of NAV) to rebalance and neutralize the breach.

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
  "proposed_trades": [
    {{
      "action": "BUY | SELL",
      "symbol": "<ticker symbol to trade>",
      "amount_pct": <float representing target percentage of portfolio NAV to trade>,
      "rationale": "<brief explanation of why this trade helps rebalance>"
    }}
  ],
  "estimated_review_time_minutes": <int>,
  "overall_verdict": "<one-line summary for dashboard display>"
}}

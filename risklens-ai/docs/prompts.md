# 📝 RiskLens AI — Prompt Engineering Guide

## Overview

RiskLens AI relies on carefully engineered prompts to ensure Claude generates accurate, consistent, and strictly formatted risk assessments. We maintain our prompts as Markdown files in the `prompts/` directory rather than hardcoding them into Python strings.

This approach ensures:
1. **Separation of Concerns:** Business logic (prompts) is decoupled from application logic.
2. **Reviewability:** Risk analysts and compliance officers can review the prompt logic without reading Python code.
3. **Version Control:** Changes to risk evaluation logic are easily trackable in Git.

---

## Directory Structure

```text
prompts/
├── severity_scoring.md         # The System Prompt (Persona & Rules)
├── concentration_analysis.md   # The User Prompt (Data Injection)
└── rebalancing_suggestion.md   # Specialized prompt for the Auto-Hedger
```

---

## The System Prompt (`severity_scoring.md`)

The system prompt establishes Claude's persona, its role, and the strict rules it must follow, particularly regarding the JSON output schema.

### Persona Definition
> "You are a senior portfolio risk analyst at a top-tier asset management firm with 15+ years of experience in risk management, concentration analysis, and regulatory compliance. Your role is to analyze pre-computed portfolio concentration data and produce structured risk assessments for portfolio managers and risk desks."

### Critical Rules Enforced
To prevent hallucination and ensure stability, the system prompt enforces these invariant rules:
1. **No Recalculation:** Claude is instructed to trust the numbers provided by the Rule Engine. It must not attempt to recalculate percentages or NAV.
2. **Focus on Interpretation:** The primary job is to explain *why* the data matters (e.g., compound risk, correlation).
3. **Volatility Awareness:** Claude is instructed to factor in provided market volatility context to adjust severity.
4. **Strict JSON:** The output must be valid JSON matching a specific schema, with absolutely no markdown wrapping or conversational filler text.

---

## The User Prompt (`concentration_analysis.md`)

The user prompt acts as a template where dynamic context is injected at runtime using LangChain's PromptTemplate system.

### Injected Variables

| Variable | Description |
|----------|-------------|
| `{portfolio_id}` | Unique identifier for the portfolio being analyzed. |
| `{fund_name}` | Name of the fund (e.g., "Alpha Growth Opportunities Fund"). |
| `{fund_type}` | The strategy type (e.g., "Multi-Asset", "Equity"). |
| `{total_nav}` | Total Net Asset Value (in INR). |
| `{rule_engine_results}`| JSON string containing hard breaches detected by the rule engine. |
| `{top_positions}`| List of the top holdings by weight to provide structural context. |
| `{market_context}`| External signals (e.g., VIX data, major market moves). |

### Example Execution Flow
1. The **Ingestion Service** receives a portfolio.
2. The **Rule Engine** evaluates the portfolio against configured limits and generates `{rule_engine_results}`.
3. The **Prompt Builder** injects this data into `concentration_analysis.md`.
4. The compiled prompt is sent to Claude.

---

## The Output Schema

Claude is instructed to return data conforming strictly to the following JSON structure. This allows the backend to deserialize the response directly into Pydantic models.

```json
{
  "severity": "LOW | MEDIUM | HIGH | CRITICAL",
  "confidence": 0.95,
  "rationale": "<2-3 sentence executive summary>",
  "breach_analysis": [
    {
      "type": "sector_concentration",
      "entity": "IT",
      "assessment": "<detailed explanation>",
      "risk_level": "HIGH"
    }
  ],
  "volatility_context": "<assessment of relevant volatility signals>",
  "historical_pattern": "<any relevant historical pattern observation>",
  "recommended_actions": [
    "Reduce exposure to IT sector by 5%",
    "Increase cash reserves"
  ],
  "proposed_trades": [
    {
      "action": "SELL",
      "symbol": "TCS.NS",
      "amount_pct": 2.5,
      "rationale": "Reduces IT sector concentration while taking profits."
    }
  ],
  "estimated_review_time_minutes": 15,
  "overall_verdict": "Critical sector concentration in IT amplified by high market volatility."
}
```

---

## Prompt Iteration & Testing

When adjusting prompts to improve the AI's risk assessment quality:
1. Modify the markdown files in the `prompts/` directory.
2. Run the `scripts/test_claude_prompts.py` script to evaluate the changes against a standard set of test portfolios in the `sample-data/` folder.
3. Review the outputs for consistency and valid JSON formatting before committing.

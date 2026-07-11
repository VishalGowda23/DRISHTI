# RiskLens AI — Prompts

This directory contains the markdown prompt templates used by Claude AI for risk analysis.
By keeping prompts in markdown files rather than hardcoded in Python, we ensure:
- Easier review by non-engineers (e.g. Risk Analysts, Product Managers)
- Clear version control of prompt changes
- Easier token estimation and testing

## Files
- `severity_scoring.md`: The system prompt defining the AI's persona, role, and strict JSON output rules.
- `concentration_analysis.md`: The user prompt containing placeholders for portfolio context, market data, and rule engine results.

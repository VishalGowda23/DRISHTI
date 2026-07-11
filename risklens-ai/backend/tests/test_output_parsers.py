import pytest
from app.domain.enums import Severity
from app.infrastructure.ai.output_parsers import parse_claude_response
from app.domain.models.risk import ClaudeAnalysis

def test_parse_claude_response_clean_json():
    raw_json = """
    {
        "severity": "MEDIUM",
        "confidence": 0.85,
        "rationale": "The portfolio has elevated concentration in Tech but is currently mitigated by low volatility context.",
        "breach_analysis": [
            {
                "type": "ISSUER",
                "entity": "Apple",
                "assessment": "Over limit due to recent stock rally",
                "risk_level": "MEDIUM"
            }
        ],
        "volatility_context": "Tech sector volatility is stable.",
        "historical_pattern": "No historical patterns detected.",
        "recommended_actions": ["Trim Apple exposure by 2%"],
        "proposed_trades": [
            {
                "action": "SELL",
                "symbol": "AAPL",
                "amount_pct": 2.0,
                "rationale": "Reduce weight to clear concentration limit"
            }
        ],
        "estimated_review_time_minutes": 10,
        "overall_verdict": "Action required"
    }
    """
    res = parse_claude_response(raw_json)
    assert isinstance(res, ClaudeAnalysis)
    assert res.severity == Severity.MEDIUM
    assert res.confidence == 0.85
    assert len(res.breach_analysis) == 1
    assert res.breach_analysis[0].entity == "Apple"
    assert len(res.proposed_trades) == 1
    assert res.proposed_trades[0].symbol == "AAPL"

def test_parse_claude_response_markdown_json():
    raw_markdown = """
    Some pre-text from Claude.
    ```json
    {
        "severity": "CRITICAL",
        "confidence": 0.95,
        "rationale": "Severe sector breach detected.",
        "breach_analysis": [],
        "volatility_context": "",
        "historical_pattern": "",
        "recommended_actions": [],
        "proposed_trades": [],
        "estimated_review_time_minutes": 5,
        "overall_verdict": "Urgent review"
    }
    ```
    Post-text from Claude.
    """
    res = parse_claude_response(raw_markdown)
    assert isinstance(res, ClaudeAnalysis)
    assert res.severity == Severity.CRITICAL
    assert res.confidence == 0.95

def test_parse_claude_response_malformed_json():
    raw_bad = """
    {
        "severity": "HIGH"
        "confidence": 0.9
    }
    """
    with pytest.raises(ValueError) as exc_info:
        parse_claude_response(raw_bad)
    assert "Invalid JSON from Claude" in str(exc_info.value)

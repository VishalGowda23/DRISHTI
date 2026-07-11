"""
RiskLens AI — Output Parsers
Strict Pydantic parsers to enforce Claude's JSON outputs match domain models.
"""

from langchain_core.output_parsers import PydanticOutputParser
from app.domain.models.risk import ClaudeAnalysis
from app.core.logger import get_logger

logger = get_logger("infrastructure.ai.parsers")

def get_assessment_parser() -> PydanticOutputParser:
    """Get the Pydantic parser for Claude's risk assessment output."""
    return PydanticOutputParser(pydantic_object=ClaudeAnalysis)

def parse_claude_response(raw_text: str) -> ClaudeAnalysis:
    """Manually parse Claude response if not using chain.invoke directly.
    
    Handles markdown json wrappers often added by Claude.
    """
    parser = get_assessment_parser()
    
    # Pre-clean markdown code blocks if present
    text = raw_text.strip()
    if "```json" in text:
        text = text.split("```json")[1].split("```")[0].strip()
    elif "```" in text:
        text = text.split("```")[1].split("```")[0].strip()
        
    try:
        return parser.parse(text)
    except Exception as e:
        logger.error(f"Failed to parse Claude output: {str(e)}\nRaw output: {raw_text}")
        raise ValueError(f"Invalid JSON from Claude: {str(e)}")

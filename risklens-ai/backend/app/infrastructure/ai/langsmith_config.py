"""
RiskLens AI — LangSmith Configuration
Sets up tracing for Claude AI invocations.
"""

import os
from langchain.callbacks.tracers import LangChainTracer
from app.core.config import get_settings
from app.core.logger import get_logger

logger = get_logger("infrastructure.ai.langsmith")

def get_tracer(portfolio_id: str = None) -> LangChainTracer:
    """Get a configured LangChain tracer for a specific portfolio."""
    settings = get_settings()
    
    # Ensure LangSmith is enabled via environment variables
    # If not explicitly disabled, we default to setting the project name
    if settings.langchain_tracing_v2:
        os.environ["LANGCHAIN_TRACING_V2"] = "true"
    
    if settings.langchain_api_key:
        os.environ["LANGCHAIN_API_KEY"] = settings.langchain_api_key
        
    os.environ["LANGCHAIN_PROJECT"] = settings.langchain_project
    
    try:
        tracer = LangChainTracer(project_name=settings.langchain_project)
        return tracer
    except Exception as e:
        logger.warning(f"Failed to initialize LangSmith tracer: {str(e)}")
        return None

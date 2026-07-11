"""
RiskLens AI — Health Check Endpoint
"""

from fastapi import APIRouter
from app.core.config import get_settings
from app.infrastructure.database.mongodb import get_database
from app.infrastructure.websocket.manager import ws_manager

router = APIRouter()


@router.get("")
async def health_check():
    """System health check with component status."""
    settings = get_settings()

    # Check MongoDB
    mongo_status = "disconnected"
    try:
        db = get_database()
        await db.command("ping")
        mongo_status = "connected"
    except Exception:
        pass

    # Check Claude API key
    claude_status = "configured" if settings.anthropic_api_key else "not_configured"

    return {
        "status": "healthy" if mongo_status == "connected" else "degraded",
        "version": settings.app_version,
        "environment": settings.app_env,
        "components": {
            "mongodb": mongo_status,
            "claude_api": claude_status,
            "websocket_connections": ws_manager.connection_count,
        },
    }

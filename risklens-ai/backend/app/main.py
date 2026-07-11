"""
RiskLens AI — FastAPI Application Entry Point
Initializes the app, middleware, routes, and lifecycle hooks.
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import get_settings
from app.core.logger import setup_logging, get_logger
from app.infrastructure.database.mongodb import connect_to_mongodb, close_mongodb
from app.infrastructure.websocket.manager import ws_manager
from app.api.router import api_router

logger = get_logger("main")


def check_environment():
    """Verify that essential environment variables are set and look valid."""
    settings = get_settings()
    # Check Anthropic API Key
    key = settings.anthropic_api_key
    if not key:
        logger.error("❌ ANTHROPIC_API_KEY is missing! Claude AI analysis will fail.")
    elif not key.startswith("sk-ant-") or len(key) < 30:
        logger.warning(
            f"⚠️ ANTHROPIC_API_KEY '{key[:10]}...' does not appear to be a valid Anthropic key (must start with 'sk-ant-' and be sufficiently long)."
        )
    else:
        logger.info("✅ ANTHROPIC_API_KEY format validation passed.")

    # Check LangChain / LangSmith configuration
    if settings.langchain_tracing_v2:
        if not settings.langchain_api_key:
            logger.warning("⚠️ LANGCHAIN_API_KEY is missing but tracing is enabled. Traces will not be sent to LangSmith.")
        else:
            logger.info("✅ LangSmith tracing configuration detected.")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifecycle manager — runs on startup and shutdown."""
    # Startup
    setup_logging()
    logger.info("🚀 Starting RiskLens AI...")
    check_environment()
    await connect_to_mongodb()
    logger.info("✅ RiskLens AI is ready")
    yield
    # Shutdown
    await close_mongodb()
    logger.info("👋 RiskLens AI shut down")


# Create FastAPI app
settings = get_settings()
app = FastAPI(
    title="RiskLens AI",
    description="Real-Time Portfolio Risk & Concentration Alert System powered by Claude AI",
    version=settings.app_version,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routes
app.include_router(api_router, prefix="/api/v1")

# --- Observability: OpenTelemetry ---
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
FastAPIInstrumentor.instrument_app(app)

# --- Rate Limiting: SlowAPI ---
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

limiter = Limiter(key_func=get_remote_address, default_limits=["100/minute"])
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

# WebSocket endpoint for real-time alerts
@app.websocket("/ws/alerts")
async def websocket_alerts(websocket: WebSocket):
    """WebSocket endpoint for real-time alert streaming."""
    await ws_manager.connect(websocket)
    try:
        while True:
            # Keep connection alive, listen for client messages
            data = await websocket.receive_text()
            # Client can send ping or acknowledgment
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)


# Root endpoint
@app.get("/")
async def root():
    return {
        "name": "RiskLens AI",
        "version": settings.app_version,
        "description": "Real-Time Portfolio Risk & Concentration Alert System",
        "docs": "/docs",
    }

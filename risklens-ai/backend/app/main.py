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


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifecycle manager — runs on startup and shutdown."""
    # Startup
    setup_logging()
    logger.info("🚀 Starting RiskLens AI...")
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

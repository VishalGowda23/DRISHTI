"""
RiskLens AI — WebSocket Connection Manager
Manages WebSocket connections for real-time alert push to frontend.
"""

from typing import Dict, List
from fastapi import WebSocket
from app.core.logger import get_logger
import json

logger = get_logger("infrastructure.websocket")


class WebSocketManager:
    """Manages active WebSocket connections and broadcasts messages."""

    def __init__(self):
        self._active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket) -> None:
        """Accept a new WebSocket connection."""
        await websocket.accept()
        self._active_connections.append(websocket)
        logger.info("WebSocket connected", total_connections=len(self._active_connections))

    def disconnect(self, websocket: WebSocket) -> None:
        """Remove a WebSocket connection."""
        if websocket in self._active_connections:
            self._active_connections.remove(websocket)
        logger.info("WebSocket disconnected", total_connections=len(self._active_connections))

    async def broadcast_alert(self, alert: dict) -> None:
        """Broadcast an alert to all connected clients."""
        message = json.dumps({
            "type": "alert",
            "data": alert,
        }, default=str)

        disconnected = []
        for connection in self._active_connections:
            try:
                await connection.send_text(message)
            except Exception:
                disconnected.append(connection)

        # Clean up disconnected clients
        for conn in disconnected:
            self.disconnect(conn)

        logger.info(
            "Alert broadcasted",
            recipients=len(self._active_connections),
            alert_severity=alert.get("severity"),
        )

    async def broadcast_assessment(self, assessment: dict) -> None:
        """Broadcast an assessment completion to all connected clients."""
        message = json.dumps({
            "type": "assessment",
            "data": assessment,
        }, default=str)

        disconnected = []
        for connection in self._active_connections:
            try:
                await connection.send_text(message)
            except Exception:
                disconnected.append(connection)

        for conn in disconnected:
            self.disconnect(conn)

    @property
    def connection_count(self) -> int:
        return len(self._active_connections)


# Singleton instance
ws_manager = WebSocketManager()

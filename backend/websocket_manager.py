"""
Trinetra FastAPI Backend — WebSocket Connection Manager
Manages active WebSocket connections per application_id.
Broadcasts agent status updates in real-time to connected frontends.
"""
import json
import asyncio
import logging
from fastapi import WebSocket
from typing import Dict, List

logger = logging.getLogger("trinetra-backend.websocket_manager")


class WebSocketManager:
    """
    Manages WebSocket connections grouped by application_id.
    When an agent publishes a status event, the backend broadcasts
    it to all frontends watching that application.
    """

    def __init__(self):
        # {application_id: [WebSocket, WebSocket, ...]}
        self.active_connections: Dict[str, List[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, application_id: str):
        """Accept a new WebSocket connection for an application."""
        await websocket.accept()
        if application_id not in self.active_connections:
            self.active_connections[application_id] = []
        self.active_connections[application_id].append(websocket)

    def disconnect(self, websocket: WebSocket, application_id: str):
        """Remove a disconnected WebSocket."""
        if application_id in self.active_connections:
            self.active_connections[application_id] = [
                ws for ws in self.active_connections[application_id]
                if ws != websocket
            ]
            if not self.active_connections[application_id]:
                del self.active_connections[application_id]

    async def broadcast_local(self, application_id: str, message: dict):
        """
        Send a message to all WebSocket clients watching this application on this local server.
        Automatically removes dead connections.
        """
        if application_id not in self.active_connections:
            return

        dead_connections = []
        for ws in self.active_connections[application_id]:
            try:
                await ws.send_json(message)
            except Exception as e:
                logger.debug(f"Failed to send websocket message, marking client as dead: {e}")
                dead_connections.append(ws)

        # Clean up dead connections
        for ws in dead_connections:
            self.disconnect(ws, application_id)

    async def broadcast(self, application_id: str, message: dict):
        """Broadcasts globally across all scaled servers via Redis Pub/Sub."""
        from core import redis_broker
        try:
            if not redis_broker.client:
                await redis_broker.connect()
            payload = {
                "application_id": application_id,
                "payload": message
            }
            await redis_broker.client.publish("websocket_broadcast", json.dumps(payload))
        except Exception as e:
            logger.warning(f"Failed to publish global websocket broadcast via Redis: {e}. Falling back to local.")
            # Fallback to local send
            await self.broadcast_local(application_id, message)

    async def broadcast_all(self, message: dict):
        """Send a message to ALL connected WebSocket clients."""
        for app_id in list(self.active_connections.keys()):
            await self.broadcast(app_id, message)

    @property
    def connection_count(self) -> int:
        """Total number of active connections."""
        return sum(len(conns) for conns in self.active_connections.values())

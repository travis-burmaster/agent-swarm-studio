"""WebSocket event manager — broadcasts Redis pub/sub to all connected clients."""

import json
import logging
from typing import Set

import redis.asyncio as aioredis
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)

router = APIRouter()


class EventManager:
    """Manages WebSocket connections and bridges Redis pub/sub."""

    def __init__(self) -> None:
        self._connections: Set[WebSocket] = set()

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self._connections.add(websocket)
        logger.info("WebSocket connected — total: %d", len(self._connections))

    def disconnect(self, websocket: WebSocket) -> None:
        self._connections.discard(websocket)
        logger.info("WebSocket disconnected — total: %d", len(self._connections))

    async def broadcast(self, message: str) -> None:
        """Send a raw string message to all connected WebSocket clients."""
        dead: Set[WebSocket] = set()
        for ws in list(self._connections):
            try:
                await ws.send_text(message)
            except Exception:
                dead.add(ws)
        for ws in dead:
            self._connections.discard(ws)

    async def broadcast_json(self, data: dict) -> None:
        await self.broadcast(json.dumps(data))

    async def subscribe(self, redis: aioredis.Redis) -> None:
        """Subscribe to 'agent:events' channel and forward to WebSocket clients."""
        pubsub = redis.pubsub()
        await pubsub.subscribe("agent:events")
        logger.info("Subscribed to Redis channel: agent:events")
        try:
            async for message in pubsub.listen():
                if message["type"] == "message":
                    await self.broadcast(message["data"])
        except Exception as exc:
            logger.error("Redis pub/sub error: %s", exc)
        finally:
            await pubsub.unsubscribe("agent:events")
            await pubsub.aclose()


# Module-level singleton
event_manager = EventManager()


@router.websocket("/ws/events")
async def websocket_events(websocket: WebSocket) -> None:
    await event_manager.connect(websocket)
    try:
        while True:
            # Keep connection alive; clients send pings as needed
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        event_manager.disconnect(websocket)

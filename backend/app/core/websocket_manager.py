from fastapi import WebSocket
from typing import List, Any
import json
import logging
import redis
import asyncio
import os
from app.core.config import settings

logger = logging.getLogger("adcom-ws")

class ConnectionManager:
    def __init__(self):
        # Active connections: [WebSocket, ...]
        self.active_connections: List[WebSocket] = []
        self.redis_url = os.getenv("REDIS_URL", "redis://127.0.0.1:6379/0")
        self._redis_client = None

    @property
    def redis(self):
        if self._redis_client is None:
            self._redis_client = redis.from_url(self.redis_url, decode_responses=True)
        return self._redis_client

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"WebSocket connected. Total connections: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
            logger.info(f"WebSocket disconnected. Remaining: {len(self.active_connections)}")

    async def broadcast(self, message: Any):
        """Send a message to all connected clients."""
        payload = json.dumps(message) if isinstance(message, (dict, list)) else str(message)

        for connection in self.active_connections:
            try:
                await connection.send_text(payload)
            except Exception as e:
                # Connection might be closed
                pass

    def publish_event(self, event_type: str, data: dict):
        """
        Helper for workers (non-async, non-FastAPI processes) 
        to publish events to Redis which will be picked up by the API process.
        """
        try:
            r = redis.from_url(self.redis_url)
            payload = json.dumps({"type": event_type, **data})
            r.publish("adcom_events", payload)
        except Exception as e:
            logger.error(f"Failed to publish WS event: {str(e)}")

    async def listen_for_events(self):
        """
        Background task for the FastAPI process to listen to Redis 
        and broadcast to all locally connected WebSockets.
        """
        pubsub = self.redis.pubsub()
        await asyncio.to_thread(pubsub.subscribe, "adcom_events")
        
        logger.info("WebSocket Manager: Listening for Redis events...")
        while True:
            try:
                # Non-blocking check for messages from Redis
                message = await asyncio.to_thread(pubsub.get_message, ignore_subscribe_messages=True, timeout=1.0)
                if message and message['type'] == 'message':
                    data = json.loads(message['data'])
                    await self.broadcast(data)
            except Exception as e:
                logger.error(f"Error in WS Redis listener: {str(e)}")
            await asyncio.sleep(0.1)

    async def notify_new_message(self, wa_id: str, message_data: dict):
        """Notify all agents about a new incoming message (Internal async call)."""
        await self.broadcast({
            "type": "new_message",
            "wa_id": wa_id,
            "data": message_data
        })

    async def notify_campaign_progress(self, campaign_id: str, stats: dict):
        """Notify all agents about campaign progress (Internal async call)."""
        await self.broadcast({
            "type": "campaign_progress",
            "campaign_id": campaign_id,
            "stats": stats
        })

manager = ConnectionManager()

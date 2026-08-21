from __future__ import annotations

import json
from typing import Any, Awaitable, Callable

import redis.asyncio as redis

from app.config import get_settings

settings = get_settings()

STREAM_EVENTS = "gusip.events"
STREAM_ALERTS = "gusip.alerts"
CHANNEL_ALERTS = "gusip.alerts.live"
CHANNEL_LIVE = "gusip.live.detections"


class EventBus:
    """Federation event bus. Redis Streams for PoC; Kafka/Redpanda swap via USE_KAFKA."""

    def __init__(self) -> None:
        self._redis: redis.Redis | None = None

    async def connect(self) -> None:
        self._redis = redis.from_url(settings.redis_url, decode_responses=True)

    async def close(self) -> None:
        if self._redis:
            await self._redis.close()

    @property
    def r(self) -> redis.Redis:
        if self._redis is None:
            raise RuntimeError("EventBus not connected")
        return self._redis

    async def publish_event(self, payload: dict[str, Any]) -> None:
        body = json.dumps(payload, default=str)
        await self.r.xadd(STREAM_EVENTS, {"data": body}, maxlen=100_000, approximate=True)
        await self.r.publish(CHANNEL_LIVE, body)

    async def publish_alert(self, payload: dict[str, Any]) -> None:
        body = json.dumps(payload, default=str)
        await self.r.xadd(STREAM_ALERTS, {"data": body}, maxlen=50_000, approximate=True)
        await self.r.publish(CHANNEL_ALERTS, body)

    async def subscribe(self, channel: str, handler: Callable[[dict[str, Any]], Awaitable[None]]) -> None:
        pubsub = self.r.pubsub()
        await pubsub.subscribe(channel)
        async for message in pubsub.listen():
            if message.get("type") != "message":
                continue
            data = json.loads(message["data"])
            await handler(data)

    async def set_json(self, key: str, value: Any, ttl: int = 30) -> None:
        await self.r.set(key, json.dumps(value, default=str), ex=ttl)

    async def get_json(self, key: str) -> Any | None:
        raw = await self.r.get(key)
        return json.loads(raw) if raw else None

    async def delete_key(self, key: str) -> None:
        await self.r.delete(key)


bus = EventBus()

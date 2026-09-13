"""Lazy singleton sync Redis client, shared by code that runs outside the
async event loop (worker threads, ffmpeg subprocess orchestration) and needs
a small amount of state shared across backend/worker replicas — the same
Redis instance app.services.event_bus already uses asynchronously.
"""

from __future__ import annotations

import redis

from app.config import get_settings

_client: redis.Redis | None = None


def get_sync_redis() -> redis.Redis:
    global _client
    if _client is None:
        _client = redis.Redis.from_url(get_settings().redis_url, decode_responses=True)
    return _client

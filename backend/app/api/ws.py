from __future__ import annotations

import asyncio
import json
from typing import Annotated

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from jose import JWTError, jwt

from app.config import get_settings
from app.services.event_bus import CHANNEL_ALERTS, CHANNEL_LIVE, bus

router = APIRouter(tags=["realtime"])
settings = get_settings()


class Hub:
    def __init__(self) -> None:
        self.clients: set[WebSocket] = set()

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        self.clients.add(ws)

    def disconnect(self, ws: WebSocket) -> None:
        self.clients.discard(ws)

    async def broadcast(self, message: dict) -> None:
        dead = []
        data = json.dumps(message, default=str)
        for ws in list(self.clients):
            try:
                await ws.send_text(data)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws)


alerts_hub = Hub()
live_hub = Hub()


def _user_from_token(token: str) -> str | None:
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
        return payload.get("sub")
    except JWTError:
        return None


@router.websocket("/ws/alerts")
async def ws_alerts(ws: WebSocket, token: str = ""):
    if not _user_from_token(token):
        await ws.close(code=4401)
        return
    await alerts_hub.connect(ws)
    try:
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        alerts_hub.disconnect(ws)


@router.websocket("/ws/live")
async def ws_live(ws: WebSocket, token: str = ""):
    if not _user_from_token(token):
        await ws.close(code=4401)
        return
    await live_hub.connect(ws)
    try:
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        live_hub.disconnect(ws)


async def relay_redis() -> None:
    async def on_alert(payload: dict) -> None:
        await alerts_hub.broadcast({"type": "alert", "data": payload})

    async def on_live(payload: dict) -> None:
        await live_hub.broadcast({"type": "detection", "data": payload})

    await asyncio.gather(
        bus.subscribe(CHANNEL_ALERTS, on_alert),
        bus.subscribe(CHANNEL_LIVE, on_live),
    )

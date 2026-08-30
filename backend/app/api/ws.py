from __future__ import annotations

import asyncio
import json

import httpx
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from jose import JWTError
from sqlalchemy import select

from app.config import get_settings
from app.core.break_glass import department_scope
from app.core.security import decode_access_token
from app.db import SessionLocal
from app.models.user import User
from app.services.event_bus import CHANNEL_ALERTS, CHANNEL_LIVE, bus

router = APIRouter(tags=["realtime"])
settings = get_settings()


class Hub:
    def __init__(self) -> None:
        self.clients: dict[WebSocket, int | None] = {}

    async def connect(self, ws: WebSocket, scoped_to: int | None) -> None:
        await ws.accept()
        self.clients[ws] = scoped_to

    def disconnect(self, ws: WebSocket) -> None:
        self.clients.pop(ws, None)

    async def broadcast(self, message: dict) -> None:
        dead = []
        data = json.dumps(message, default=str)
        department_id = message.get("department_id")
        for ws, scoped_to in list(self.clients.items()):
            if scoped_to is not None and department_id != scoped_to:
                continue
            try:
                await ws.send_text(data)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws)


alerts_hub = Hub()
live_hub = Hub()


async def _principal_from_ws(ws: WebSocket) -> tuple[str, int | None] | None:
    token = ws.cookies.get(settings.session_cookie_name)
    if not token:
        return None
    try:
        payload = await decode_access_token(token)
        username = payload.get(settings.oidc_username_claim) if settings.auth_provider == "oidc" else payload.get("sub")
    except (JWTError, httpx.HTTPError):
        return None
    if not username:
        return None
    async with SessionLocal() as db:
        user = await db.scalar(select(User).where(User.username == username, User.is_active.is_(True)))
        if user is None:
            return None
        return user.username, await department_scope(user)


async def _serve(ws: WebSocket, hub: Hub) -> None:
    principal = await _principal_from_ws(ws)
    if principal is None:
        await ws.close(code=4401)
        return
    _, scoped_to = principal
    await hub.connect(ws, scoped_to)
    try:
        while True:
            try:
                await asyncio.wait_for(ws.receive_text(), timeout=60)
            except asyncio.TimeoutError:
                refreshed = await _principal_from_ws(ws)
                if refreshed is None:
                    await ws.close(code=4401)
                    return
                hub.clients[ws] = refreshed[1]
    except WebSocketDisconnect:
        pass
    finally:
        hub.disconnect(ws)


@router.websocket("/ws/alerts")
async def ws_alerts(ws: WebSocket):
    await _serve(ws, alerts_hub)


@router.websocket("/ws/live")
async def ws_live(ws: WebSocket):
    await _serve(ws, live_hub)


async def relay_redis() -> None:
    async def on_alert(payload: dict) -> None:
        await alerts_hub.broadcast({"type": "alert", "data": payload})

    async def on_live(payload: dict) -> None:
        await live_hub.broadcast({"type": "detection", "data": payload})

    await asyncio.gather(
        bus.subscribe(CHANNEL_ALERTS, on_alert),
        bus.subscribe(CHANNEL_LIVE, on_live),
    )

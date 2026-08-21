from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Annotated

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import Response, StreamingResponse
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import get_settings
from app.core.audit import write_audit
from app.core.policy import has_capability
from app.core.security import client_ip, get_current_user
from app.db import get_db
from app.models.event import DetectionEvent
from app.models.user import User
from app.workers.sentinel import PREVIEW_DIR, fetch_catalog, fetch_state, sync_catalog

router = APIRouter(prefix="/feeds", tags=["feeds"])
settings = get_settings()


def _require_token(token: str | None) -> None:
    if not token:
        raise HTTPException(401, "Token required")
    try:
        jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
    except JWTError:
        raise HTTPException(401, "Invalid token")


@router.post("/sentinel/sync")
async def sync_now(_user: Annotated[User, Depends(get_current_user)]):
    n = await sync_catalog()
    return {"synced": n, "source": settings.sentinel_base_url}


@router.get("/sentinel/catalog")
async def catalog(_user: Annotated[User, Depends(get_current_user)]):
    cams = await fetch_catalog()
    return {"count": len(cams), "cameras": cams, "source": settings.sentinel_base_url}


@router.get("/sentinel/{sentinel_id}/state")
async def camera_state(sentinel_id: str, _user: Annotated[User, Depends(get_current_user)]):
    try:
        return await fetch_state(sentinel_id)
    except httpx.HTTPError as exc:
        raise HTTPException(502, f"Sentinel state unavailable: {exc}") from exc


@router.get("/sentinel/{sentinel_id}/preview")
async def preview(sentinel_id: str, token: str | None = Query(default=None)):
    _require_token(token)
    path = PREVIEW_DIR / f"SEN-{sentinel_id}.jpg"
    if not path.exists():
        raise HTTPException(404, "No preview yet — ANPR sampler has not grabbed this camera")
    return Response(content=path.read_bytes(), media_type="image/jpeg")


@router.get("/sentinel/{sentinel_id}/stream")
async def proxy_stream(sentinel_id: str, request: Request, token: str | None = Query(default=None)):
    _require_token(token)
    url = f"{settings.sentinel_base_url.rstrip('/')}/stream/{sentinel_id}"
    headers = {"User-Agent": "GUSIP-Sentinel-Adapter/1.0"}
    rng = request.headers.get("range")
    if rng:
        headers["Range"] = rng

    client = httpx.AsyncClient(timeout=60.0, follow_redirects=True)
    req = client.build_request("GET", url, headers=headers)
    try:
        resp = await client.send(req, stream=True)
    except httpx.HTTPError as exc:
        await client.aclose()
        raise HTTPException(502, f"Upstream feed error: {exc}") from exc

    out: dict[str, str] = {}
    for key in ("content-type", "content-length", "content-range", "accept-ranges", "etag", "cache-control"):
        if key in resp.headers:
            out[key] = resp.headers[key]

    async def body():
        try:
            async for chunk in resp.aiter_bytes(64 * 1024):
                yield chunk
        finally:
            await resp.aclose()
            await client.aclose()

    return StreamingResponse(body(), status_code=resp.status_code, headers=out, media_type=out.get("content-type"))


@router.get("/anpr-report")
async def anpr_report(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
    hours: int = 24,
    fmt: str = "json",
):
    if fmt == "csv" and not has_capability(user, "export"):
        raise HTTPException(403, "Your role cannot export ANPR reports")
    since = datetime.now(timezone.utc) - timedelta(hours=hours)
    q = (
        select(DetectionEvent)
        .options(selectinload(DetectionEvent.camera))
        .where(DetectionEvent.event_type == "anpr", DetectionEvent.timestamp >= since)
        .order_by(DetectionEvent.timestamp.desc())
        .limit(2000)
    )
    rows = list((await db.execute(q)).scalars())
    payload = [
        {
            "timestamp": e.timestamp.isoformat() if e.timestamp else None,
            "camera_code": e.camera.code if e.camera else None,
            "camera_name": e.camera.name if e.camera else None,
            "location": (e.camera.address if e.camera else None) or (e.attributes or {}).get("official_location"),
            "city": e.camera.city if e.camera else None,
            "plate": e.plate_number,
            "plate_normalized": e.plate_normalized,
            "confidence": e.confidence,
            "snapshot_url": e.snapshot_url,
            "source": (e.attributes or {}).get("source_type"),
            "global_track_id": e.global_track_id,
        }
        for e in rows
    ]
    if fmt == "csv":
        import csv
        import io

        await write_audit(
            db,
            user_id=user.id,
            username=user.username,
            action="export_anpr_csv",
            resource="feeds/anpr-report",
            details={"hours": hours, "rows": len(payload)},
            ip_address=client_ip(request),
            department_id=user.department_id,
        )
        await db.commit()
        buf = io.StringIO()
        w = csv.DictWriter(buf, fieldnames=list(payload[0].keys()) if payload else ["timestamp", "plate"])
        w.writeheader()
        w.writerows(payload)
        return Response(content=buf.getvalue(), media_type="text/csv")
    return {"count": len(payload), "hours": hours, "rows": payload}

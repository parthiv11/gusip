from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Annotated
import re
from urllib.parse import urljoin, urlsplit

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse, Response, StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import get_settings
from app.core.audit import write_audit
from app.core.break_glass import department_scope
from app.core.policy import has_capability, require_capability
from app.core.security import client_ip, get_current_user
from app.db import get_db
from app.models.camera import Camera
from app.models.event import DetectionEvent
from app.models.user import User
from app.services.local_feed import ensure_demo_loop, ensure_still_loop
from app.services.sentinel_auth import apply_session
from app.workers.sentinel import PREVIEW_DIR, fetch_catalog, fetch_state, sync_catalog, validate_sentinel_url

router = APIRouter(prefix="/feeds", tags=["feeds"])
settings = get_settings()
UPSTREAM_MEDIA_FIELDS = {
    "rtsp_url",
    "hls_url",
    "hls_live_url",
    "whep_url",
    "webrtc_url",
    "stream_url",
    "portal",
}


def _public_catalogue_camera(camera: dict) -> dict:
    return {key: value for key, value in camera.items() if key not in UPSTREAM_MEDIA_FIELDS}


async def _send_upstream_stream(
    client: httpx.AsyncClient,
    url: str,
    headers: dict[str, str],
    max_redirects: int = 5,
) -> httpx.Response:
    current = url
    for _ in range(max_redirects + 1):
        validate_sentinel_url(current)
        response = await client.send(client.build_request("GET", current, headers=headers), stream=True)
        if not response.is_redirect:
            return response
        location = response.headers.get("location")
        await response.aclose()
        if not location:
            return response
        if "/auth/login" in location:
            raise httpx.HTTPError("Sentinel feed requires upstream login")
        current = urljoin(str(response.url), location)
    raise httpx.TooManyRedirects("Sentinel redirect limit exceeded")


async def _authorize_sentinel_camera(
    db: AsyncSession,
    user: User,
    sentinel_id: str,
) -> Camera:
    camera = await db.scalar(select(Camera).where(Camera.code == f"SEN-{sentinel_id}", Camera.is_active.is_(True)))
    if camera is None:
        raise HTTPException(404, "Unknown Sentinel camera")
    # SCRB evaluation wall is visible to any signed-in live-wall user.
    return camera


def _portal_id(camera: Camera, sentinel_id: str) -> str:
    extra = camera.extra or {}
    return str(extra.get("portal_id") or extra.get("sentinel_id") or sentinel_id)


def _rewrite_grid_playlist(body: str, sentinel_id: str) -> str:
    prefix = f"/api/v1/feeds/sentinel/{sentinel_id}/hls/"
    lines: list[str] = []
    for line in body.splitlines():
        if line.startswith("#") and "URI=" in line:
            line = re.sub(r'URI="[^"]+"', f'URI="{prefix}enc.key"', line)
        elif line and not line.startswith("#"):
            name = urlsplit(line).path.rsplit("/", 1)[-1]
            if name:
                line = prefix + name
        lines.append(line)
    return "\n".join(lines) + "\n"


@router.post("/sentinel/sync")
async def sync_now(_user: Annotated[User, Depends(require_capability("onboard_camera"))]):
    n = await sync_catalog()
    return {"synced": n, "source": "sentinel"}


@router.get("/sentinel/catalog")
async def catalog(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
):
    cams = await fetch_catalog()
    scoped_to = await department_scope(user)
    if scoped_to is not None:
        allowed = set(
            (
                await db.scalars(
                    select(Camera.code).where(
                        Camera.department_id == scoped_to,
                        Camera.source_type == "sentinel",
                        Camera.is_active.is_(True),
                    )
                )
            ).all()
        )
        cams = [camera for camera in cams if f"SEN-{camera.get('id')}" in allowed]
    return {"count": len(cams), "cameras": [_public_catalogue_camera(camera) for camera in cams], "source": "sentinel"}


@router.get("/sentinel/{sentinel_id}/state")
async def camera_state(
    sentinel_id: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
):
    await _authorize_sentinel_camera(db, user, sentinel_id)
    try:
        return await fetch_state(sentinel_id)
    except httpx.HTTPError as exc:
        raise HTTPException(502, f"Sentinel state unavailable: {exc}") from exc


@router.get("/sentinel/{sentinel_id}/preview")
async def preview(
    sentinel_id: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
):
    await _authorize_sentinel_camera(db, user, sentinel_id)
    path = PREVIEW_DIR / f"SEN-{sentinel_id}.jpg"
    if not path.exists():
        raise HTTPException(404, "No preview yet — ANPR sampler has not grabbed this camera")
    return Response(content=path.read_bytes(), media_type="image/jpeg")


@router.get("/sentinel/{sentinel_id}/hls/{asset:path}")
async def proxy_grid_hls(
    sentinel_id: str,
    asset: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
):
    """Same-origin HLS for the wall. Session cookie stays on the API, not in the browser."""
    camera = await _authorize_sentinel_camera(db, user, sentinel_id)
    if ".." in asset or asset.startswith("/") or not asset:
        raise HTTPException(400, "Invalid HLS asset")
    origin = settings.sentinel_base_url.rstrip("/")
    portal = _portal_id(camera, sentinel_id)
    extra = camera.extra or {}
    if asset == "enc.key":
        url = f"{origin}/enc.key"
    elif asset.endswith(".m3u8"):
        url = str(extra.get("hls_url") or f"{origin}/{portal}/index.m3u8")
    else:
        url = f"{origin}/{portal}/{asset}"
    try:
        validate_sentinel_url(url)
    except ValueError as exc:
        raise HTTPException(502, str(exc)) from exc
    headers = apply_session(settings.sentinel_headers(accept="*/*"))
    headers["Referer"] = f"{origin}/"
    headers["Origin"] = origin
    client = httpx.AsyncClient(timeout=45.0, follow_redirects=False)
    try:
        resp = await _send_upstream_stream(client, url, headers)
    except (httpx.HTTPError, ValueError) as exc:
        await client.aclose()
        raise HTTPException(502, f"Upstream feed error: {exc}") from exc
    ctype = (resp.headers.get("content-type") or "").lower()
    if resp.status_code >= 400 or "html" in ctype:
        await resp.aclose()
        await client.aclose()
        raise HTTPException(502, "Sentinel HLS unavailable")
    if asset.endswith(".m3u8") or "mpegurl" in ctype:
        body = await resp.aread()
        await resp.aclose()
        await client.aclose()
        rewritten = _rewrite_grid_playlist(body.decode("utf-8", "replace"), sentinel_id)
        return Response(
            content=rewritten,
            media_type="application/vnd.apple.mpegurl",
            headers={"Cache-Control": "no-store"},
        )

    out: dict[str, str] = {"Cache-Control": "no-store"}
    for key in ("content-type", "content-length", "accept-ranges"):
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


@router.get("/sentinel/{sentinel_id}/stream")
async def proxy_stream(
    sentinel_id: str,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
):
    """Browser range-request fallback. AI ingest uses RTSP/HLS from /api/ingest, not this path."""
    await _authorize_sentinel_camera(db, user, sentinel_id)
    origin = settings.sentinel_base_url.rstrip("/")
    url = f"{origin}/stream/{sentinel_id}"
    headers = apply_session(settings.sentinel_headers(accept="*/*"))
    headers["Referer"] = f"{origin}/"
    headers["Origin"] = origin
    rng = request.headers.get("range")
    if rng:
        headers["Range"] = rng

    client = httpx.AsyncClient(timeout=60.0, follow_redirects=False)
    try:
        resp = await _send_upstream_stream(client, url, headers)
        ctype = (resp.headers.get("content-type") or "").lower()
        if resp.status_code < 400 and "html" not in ctype and "text/" not in ctype:
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
        await resp.aclose()
        await client.aclose()
    except (httpx.HTTPError, ValueError):
        await client.aclose()

    local = ensure_still_loop(sentinel_id)
    if local is None:
        raise HTTPException(502, "Upstream feed unavailable and no local loop is ready")
    return FileResponse(local, media_type="video/mp4", headers={"Accept-Ranges": "bytes", "Cache-Control": "no-store"})


@router.get("/demo/loop")
async def demo_loop(_user: Annotated[User, Depends(get_current_user)]):
    """Placeholder clip for departmental cameras when no vendor stream is attached."""
    local = ensure_demo_loop()
    if local is None:
        raise HTTPException(503, "Demo loop is not ready")
    return FileResponse(local, media_type="video/mp4", headers={"Accept-Ranges": "bytes", "Cache-Control": "no-store"})


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
    scoped_to = await department_scope(user)
    q = (
        select(DetectionEvent)
        .join(Camera, Camera.id == DetectionEvent.camera_id)
        .options(selectinload(DetectionEvent.camera))
        .where(DetectionEvent.event_type == "anpr", DetectionEvent.timestamp >= since)
        .order_by(DetectionEvent.timestamp.desc())
        .limit(2000)
    )
    if scoped_to is not None:
        q = q.where(Camera.department_id == scoped_to)
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

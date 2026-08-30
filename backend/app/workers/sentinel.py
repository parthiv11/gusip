"""Official Sentinel sandbox adapter.

Contract: https://sentinel.gujarat.gov.in/resource

- Catalogue is GET /api/ingest. IDs and URLs are dynamic; never hard-code them.
- AI/inference uses rtsp://<host>:8554/stream/<id> over TCP.
- If :8554 is blocked, use HLS /live/stream/<id>/index.m3u8.
- WHEP :8889/stream/<id>/whep is browser preview only.
- HTTP /stream/<id> is a media-player range fallback — never the ANPR/YOLO path,
  and never downloaded with curl/wget as if it were a file.
- Timing is PTS, not wall clock or reported FPS.
- Reconnect with 2–30s backoff. Join decoder warnings are not fatal.
- Feeds loop; a PTS regression is a scene cut (reset trackers).
- Consume only. Do not publish or call gateway control APIs.
- Pace load: one live capture at a time, then close it.
"""

from __future__ import annotations

import asyncio
import logging
import os
import shutil
import socket
import subprocess
import tempfile
import threading
import time
from datetime import datetime, timedelta, timezone
from io import BytesIO
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlencode, urljoin, urlsplit, urlunsplit

import httpx
from geoalchemy2.elements import WKTElement
from PIL import Image
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from app.config import get_settings
from app.db import SessionLocal
from app.models.camera import Camera, Department
from app.services.anpr import extract_plates
from app.services.plate_ocr import plate_crops, read_plate_text
from app.services.pipeline import ingest_detection
from app.services.storage import DATA_DIR, save_snapshot_png
from app.workers.sentinel_geo import geocode

log = logging.getLogger("gusip.sentinel")
settings = get_settings()
PREVIEW_DIR = DATA_DIR / "previews"
_rtsp_retry_at = 0.0
_rtsp_failures = 0
_local_pub: subprocess.Popen | None = None
_local_sid: str | None = None
JOIN_DECODER_HINTS = (
    "Error constructing the frame RPS",
    "Could not find ref with POC",
)
os.environ.setdefault("OPENCV_FFMPEG_CAPTURE_OPTIONS", "rtsp_transport;tcp")


def _is_join_decoder_warning(text: str) -> bool:
    return any(hint in text for hint in JOIN_DECODER_HINTS)


def _report_feed(level: int, camera_id: str, url: str, client: str, error: str) -> None:
    log.log(
        level,
        "sentinel feed id=%s url=%s client=%s utc=%s err=%s",
        camera_id or "-",
        url,
        client,
        datetime.now(timezone.utc).isoformat(),
        error[:500],
    )


def validate_sentinel_url(url: str, allowed_schemes: frozenset[str] = frozenset({"https"})) -> str:
    parsed = urlsplit(url)
    host = (parsed.hostname or "").lower()
    allowed_hosts = set(settings.sentinel_allowed_host_set)
    local = urlsplit(settings.sentinel_local_rtsp_url)
    if local.hostname and parsed.scheme.lower() == "rtsp":
        allowed_hosts.add(local.hostname.lower())
    if parsed.scheme.lower() not in allowed_schemes or host not in allowed_hosts:
        raise ValueError(f"Sentinel URL is outside the configured allowlist: {parsed.scheme}://{host}")
    if parsed.username or parsed.password:
        raise ValueError("Sentinel URLs must not contain user info")
    return url


def rewrite_hls_location(request_url: str, location: str) -> str:
    """MediaMTX cookieCheck 302s to /stream/<id>/…; the public proxy lives at /live/stream/<id>/."""
    joined = urljoin(request_url, location)
    req = urlsplit(request_url)
    loc = urlsplit(joined)
    if loc.path.startswith("/stream/") and "/live/stream/" in (req.path or ""):
        loc = loc._replace(path="/live" + loc.path)
    # cookieCheck 302s to http://; stay on HTTPS so the allowlist and CF proxy both work.
    if loc.scheme == "http" and (loc.hostname or "").lower() in settings.sentinel_allowed_host_set:
        loc = loc._replace(scheme="https")
    return urlunsplit(loc)


async def _async_get_with_redirects(
    client: httpx.AsyncClient,
    url: str,
    *,
    headers: dict[str, str] | None = None,
    max_redirects: int = 5,
) -> httpx.Response:
    current = url
    for _ in range(max_redirects + 1):
        validate_sentinel_url(current)
        response = await client.get(current, headers=headers)
        if not response.is_redirect:
            return response
        location = response.headers.get("location")
        if not location:
            return response
        current = rewrite_hls_location(str(response.url), location)
    raise httpx.TooManyRedirects("Sentinel redirect limit exceeded")


HLS_SESSION_COOKIE = "hlsSession"
HLS_SESSION_QUERY = "session"
HLS_COOKIE_CHECK = "cookieCheck"


def _header_list(headers: httpx.Headers, name: str) -> list[str]:
    if hasattr(headers, "get_list"):
        return headers.get_list(name)
    if hasattr(headers, "getlist"):
        return headers.getlist(name)
    value = headers.get(name)
    return [value] if value else []


def _set_cookie(client: httpx.Client, name: str, value: str, url: str) -> None:
    host = urlsplit(url).hostname
    if not host or not value:
        return
    for cookie in list(client.cookies.jar):
        if cookie.name == name:
            try:
                client.cookies.jar.clear(cookie.domain, cookie.path, cookie.name)
            except KeyError:
                pass
    client.cookies.set(name, value, domain=host, path="/")


def _capture_hls_cookies(client: httpx.Client, response: httpx.Response, url: str) -> str | None:
    """Keep MediaMTX session cookies on Path=/ and recover ?session= when Partitioned cookies are dropped."""
    secret: str | None = None
    headers = response.headers
    raw_cookies = _header_list(headers, "set-cookie")
    for raw in raw_cookies:
        first = raw.split(";", 1)[0]
        if "=" not in first:
            continue
        name, value = first.split("=", 1)
        name, value = name.strip(), value.strip()
        if name in {HLS_COOKIE_CHECK, HLS_SESSION_COOKIE} and value:
            _set_cookie(client, name, value, url)
            if name == HLS_SESSION_COOKIE:
                secret = value
    for cookie in list(client.cookies.jar):
        if cookie.name in {HLS_COOKIE_CHECK, HLS_SESSION_COOKIE} and cookie.value:
            _set_cookie(client, cookie.name, cookie.value, url)
            if cookie.name == HLS_SESSION_COOKIE:
                secret = cookie.value
    query = dict(parse_qsl(urlsplit(str(response.url)).query, keep_blank_values=True))
    if query.get(HLS_SESSION_QUERY):
        secret = secret or query[HLS_SESSION_QUERY]
        _set_cookie(client, HLS_SESSION_COOKIE, secret, url)
    return secret


def _with_session(url: str, secret: str | None) -> str:
    if not secret:
        return url
    parts = urlsplit(url)
    query = dict(parse_qsl(parts.query, keep_blank_values=True))
    query[HLS_SESSION_QUERY] = secret
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))


def _get_with_redirects(
    client: httpx.Client,
    url: str,
    *,
    headers: dict[str, str] | None = None,
    max_redirects: int = 5,
) -> httpx.Response:
    current = url
    for _ in range(max_redirects + 1):
        validate_sentinel_url(current)
        response = client.get(current, headers=headers)
        secret = _capture_hls_cookies(client, response, current)
        if not response.is_redirect:
            return response
        location = response.headers.get("location")
        if not location:
            return response
        current = _with_session(rewrite_hls_location(str(response.url), location), secret)
    raise httpx.TooManyRedirects("Sentinel redirect limit exceeded")


def _rtsp_available(now: float | None = None) -> bool:
    return settings.sentinel_rtsp_enabled and (now if now is not None else time.monotonic()) >= _rtsp_retry_at


def _mark_rtsp_failure(now: float | None = None) -> float:
    global _rtsp_failures, _rtsp_retry_at
    _rtsp_failures += 1
    delay = min(30.0, 2.0 * (2 ** (_rtsp_failures - 1)))
    _rtsp_retry_at = (now if now is not None else time.monotonic()) + delay
    return delay


def _mark_rtsp_success() -> None:
    global _rtsp_failures, _rtsp_retry_at
    _rtsp_failures = 0
    _rtsp_retry_at = 0.0


def _abs(url: str | None) -> str | None:
    if not url:
        return None
    if url.startswith("http") or url.startswith("rtsp://"):
        return url
    return f"{settings.sentinel_base_url.rstrip('/')}{url}"


def _camera_list(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [x for x in payload if isinstance(x, dict)]
    if isinstance(payload, dict):
        for key in ("cameras", "data", "feeds"):
            rows = payload.get(key)
            if isinstance(rows, list):
                return [x for x in rows if isinstance(x, dict)]
    return []


def _is_live(item: dict[str, Any]) -> bool:
    if item.get("live") is True:
        return True
    if item.get("live") is False:
        return False
    return str(item.get("status") or "").lower() in {"live", "online", "processing"}


def normalize_camera(item: dict[str, Any], base_url: str | None = None) -> dict[str, Any]:
    """Map /api/ingest (or /api/cameras) into one shape. Catalogue is the contract."""
    base = (base_url or settings.sentinel_base_url).rstrip("/")
    sid = str(item.get("id") or item.get("number") or "")
    hls = item.get("hls_live_url") or item.get("hls_url")
    whep = item.get("webrtc_url") or item.get("whep_url")
    rtsp = item.get("rtsp_url")
    live = _is_live(item)

    def abs_http(url: str | None) -> str | None:
        if not url:
            return None
        candidate = url if url.startswith("http") or url.startswith("rtsp://") else f"{base}{url}"
        schemes = frozenset({"rtsp"}) if candidate.startswith("rtsp://") else frozenset({"http", "https"})
        try:
            return validate_sentinel_url(candidate, schemes)
        except ValueError:
            log.warning("discarding non-allowlisted Sentinel media URL")
            return None

    if rtsp:
        rtsp = abs_http(rtsp)

    return {
        "id": sid,
        "name": item.get("name") or f"Sentinel {sid}",
        "location": item.get("location") or item.get("name") or f"SEN-{sid}",
        "codec": item.get("codec") or "",
        "live": live,
        "width": int(item.get("width") or 0),
        "height": int(item.get("height") or 0),
        # Catalogue FPS is metadata only — never use it for speed, dwell, or timestamps.
        "fps": float(item.get("fps") or 0),
        "bitrate_kbps": item.get("bitrate_kbps") or 0,
        "rtsp_url": rtsp,
        "whep_url": abs_http(whep),
        "hls_url": abs_http(hls),
        # Documented browser range-request fallback, not an inference URL.
        "stream_url": abs_http(f"/stream/{sid}") if sid else None,
        "container": item.get("container"),
        "status": "live" if live else str(item.get("status") or "offline"),
    }


def inference_urls(extra: dict[str, Any] | None) -> list[str]:
    """RTSP first while :8554 is reachable. HLS otherwise. Never HTTP /stream."""
    extra = extra or {}
    urls: list[str] = []
    if settings.sentinel_rtsp_enabled and _rtsp_available():
        rtsp = extra.get("rtsp_url")
        if isinstance(rtsp, str) and rtsp:
            urls.append(rtsp)
    hls = extra.get("hls_url")
    if isinstance(hls, str) and hls and hls not in urls:
        urls.append(hls)
    return urls


def inference_url(extra: dict[str, Any] | None) -> str | None:
    urls = inference_urls(extra)
    return urls[0] if urls else None


def grab_cmd(url: str, ffmpeg: str = "ffmpeg") -> list[str]:
    # Native resolution: mixed H.264/H.265 and frame sizes come from the catalogue.
    # No -ss: live RTP has no seeking. -copyts keeps PTS for timing.
    cmd = [ffmpeg, "-hide_banner", "-loglevel", "warning", "-nostats", "-progress", "pipe:2", "-copyts"]
    if url.startswith("rtsp://"):
        validate_sentinel_url(url, frozenset({"rtsp"}))
        cmd += ["-rtsp_transport", "tcp", "-timeout", "3000000"]
    else:
        if url.startswith(("http://", "https://")):
            validate_sentinel_url(url, frozenset({"http", "https"}))
            player = _hls_player_headers(url)
            cmd += [
                "-rw_timeout",
                "8000000",
                "-user_agent",
                player["User-Agent"],
                "-headers",
                f"Referer: {player['Referer']}\r\nOrigin: {player['Origin']}\r\n",
            ]
    cmd += [
        "-i",
        url,
        "-frames:v",
        "1",
        "-an",
        "-c:v",
        "mjpeg",
        "-q:v",
        "3",
        "-f",
        "image2",
        "pipe:1",
    ]
    return cmd


def _parse_progress_pts(stderr: str) -> float | None:
    result: float | None = None
    for line in stderr.splitlines():
        key, _, value = line.partition("=")
        if key == "out_time_us":
            try:
                candidate = int(value) / 1_000_000
                if candidate >= 0:
                    result = candidate
            except ValueError:
                continue
        if key == "out_time":
            try:
                hours, minutes, seconds = value.split(":")
                candidate = int(hours) * 3600 + int(minutes) * 60 + float(seconds)
                if candidate >= 0:
                    result = candidate
            except (ValueError, TypeError):
                continue
    return result


def advance_stream_clock(
    extra: dict[str, Any],
    pts: float | None,
    now: datetime | None = None,
) -> tuple[datetime, int]:
    captured_at = now or datetime.now(timezone.utc)
    epoch = int(extra.get("stream_epoch") or 0)
    if pts is None:
        return captured_at, epoch

    last_pts = extra.get("stream_last_pts")
    if last_pts is not None and pts < float(last_pts) - 0.5:
        epoch += 1
        extra["stream_epoch"] = epoch
        extra["stream_base_pts"] = pts
        extra["stream_base_time"] = captured_at.isoformat()
    elif extra.get("stream_base_pts") is None or extra.get("stream_base_time") is None:
        extra["stream_base_pts"] = pts
        extra["stream_base_time"] = captured_at.isoformat()

    base_time = datetime.fromisoformat(str(extra["stream_base_time"]).replace("Z", "+00:00"))
    if base_time.tzinfo is None:
        base_time = base_time.replace(tzinfo=timezone.utc)
    timestamp = base_time + timedelta(seconds=max(0.0, pts - float(extra["stream_base_pts"])))
    extra["stream_last_pts"] = pts
    extra["stream_epoch"] = epoch
    return timestamp, epoch


async def fetch_catalog() -> list[dict[str, Any]]:
    """Camera list and URLs come from GET /api/ingest. IDs are not hard-coded."""
    base = settings.sentinel_base_url.rstrip("/")
    async with httpx.AsyncClient(timeout=30.0, follow_redirects=False, headers=settings.sentinel_headers()) as client:
        for path in ("/api/ingest", "/api/cameras"):
            try:
                r = await _async_get_with_redirects(client, f"{base}{path}")
                if r.status_code >= 400:
                    log.warning("catalogue %s -> %s", path, r.status_code)
                    continue
                cams = _camera_list(r.json())
                if cams:
                    log.info("sentinel catalogue %s n=%s", path, len(cams))
                    return [normalize_camera(c, str(r.url).rsplit(path, 1)[0] or base) for c in cams]
            except Exception:
                log.exception("catalogue %s failed", path)
    return []


async def fetch_state(cam_id: str) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=20.0, follow_redirects=False, headers=settings.sentinel_headers()) as client:
        r = await _async_get_with_redirects(
            client,
            f"{settings.sentinel_base_url.rstrip('/')}/api/cameras/{cam_id}/state",
        )
        r.raise_for_status()
        return r.json()


async def ensure_department(db: AsyncSession) -> Department:
    row = (await db.execute(select(Department).where(Department.code == "SENT"))).scalar_one_or_none()
    if row:
        return row
    dept = Department(code="SENT", name="Sentinel Evaluation Feeds (SCRB)", zone="Gujarat")
    db.add(dept)
    await db.flush()
    return dept


async def sync_catalog() -> int:
    cams = await fetch_catalog()
    async with SessionLocal() as db:
        dept = await ensure_department(db)
        existing = {
            c.code: c
            for c in (await db.execute(select(Camera).where(Camera.source_type == "sentinel"))).scalars()
        }
        seen: set[str] = set()
        for item in cams:
            sid = str(item.get("id") or "")
            if not sid:
                continue
            code = f"SEN-{sid}"
            seen.add(code)
            loc = item.get("location") or item.get("name") or code
            lat, lon, city = geocode(loc)
            status = "online" if item.get("live") else "offline"
            extra = {
                "sentinel_id": sid,
                "live": bool(item.get("live")),
                "rtsp_url": item.get("rtsp_url"),
                "whep_url": item.get("whep_url"),
                "hls_url": item.get("hls_url"),
                "stream_url": item.get("stream_url"),
                "codec": item.get("codec"),
                "width": item.get("width"),
                "height": item.get("height"),
                "fps": item.get("fps"),
                "bitrate_kbps": item.get("bitrate_kbps"),
                "container": item.get("container"),
                "official_location": loc,
                "portal": settings.sentinel_base_url,
                "catalogue": "api/ingest",
            }
            cam = existing.get(code)
            if cam:
                cam.name = item.get("name") or cam.name
                cam.address = loc
                cam.city = city
                cam.status = status
                cam.latitude = lat
                cam.longitude = lon
                cam.location = WKTElement(f"POINT({lon} {lat})", srid=4326)
                cam.last_seen_at = datetime.now(timezone.utc)
                cam.extra = {**(cam.extra or {}), **extra}
                flag_modified(cam, "extra")
                cam.is_active = True
            else:
                db.add(
                    Camera(
                        code=code,
                        name=item.get("name") or f"Sentinel {sid}",
                        department_id=dept.id,
                        camera_type="ip",
                        ownership="Gujarat Police / SCRB evaluation",
                        source_type="sentinel",
                        vendor="Sentinel live-feed simulator",
                        vendor_api_ref=f"sentinel:{sid}",
                        status=status,
                        connectivity="evaluation-portal",
                        storage_details="Source remains on Sentinel (not centralised)",
                        amc_status="evaluation",
                        coverage_radius_m=80,
                        location=WKTElement(f"POINT({lon} {lat})", srid=4326),
                        latitude=lat,
                        longitude=lon,
                        city=city,
                        address=loc,
                        extra=extra,
                        last_seen_at=datetime.now(timezone.utc),
                        is_active=True,
                    )
                )
        for code, cam in existing.items():
            if code not in seen:
                cam.status = "offline"
        await db.commit()
    log.info("synced %s sentinel cameras", len(cams))
    return len(cams)


def _playlist_refs(body: str, base: str, session: str | None = None) -> list[str]:
    parent = urlsplit(base)
    parent_q = dict(parse_qsl(parent.query, keep_blank_values=True))
    refs: list[str] = []
    for line in body.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if line.lower().startswith("gap."):
            continue
        child = urlsplit(urljoin(base, line))
        child_q = dict(parse_qsl(child.query, keep_blank_values=True))
        q = {k: v for k, v in {**parent_q, **child_q}.items() if k != HLS_COOKIE_CHECK}
        if session:
            q[HLS_SESSION_QUERY] = session
        candidate = urlunsplit((child.scheme, child.netloc, child.path, urlencode(q), child.fragment))
        validate_sentinel_url(candidate)
        refs.append(candidate)
    return refs


def _hls_player_headers(url: str, accept: str = "*/*") -> dict[str, str]:
    parts = urlsplit(url)
    origin = f"{parts.scheme}://{parts.netloc}"
    bits = [p for p in parts.path.split("/") if p]
    camera_id = bits[2] if len(bits) >= 3 and bits[0] == "live" and bits[1] == "stream" else ""
    referer = f"{origin}/camera/{camera_id}" if camera_id else f"{origin}/"
    return {
        "User-Agent": settings.sentinel_user_agent,
        "Accept": accept,
        "Referer": referer,
        "Origin": origin,
    }


def _hls_secret(client: httpx.Client, url: str) -> str | None:
    query = dict(parse_qsl(urlsplit(url).query, keep_blank_values=True))
    if query.get(HLS_SESSION_QUERY):
        return query[HLS_SESSION_QUERY]
    for cookie in client.cookies.jar:
        if cookie.name == HLS_SESSION_COOKIE and cookie.value:
            return cookie.value
    return None


def _fetch_hls_segment_once(url: str) -> tuple[bytes | None, bool]:
    """Return a segment and whether a fresh HLS handshake should be retried."""
    headers = _hls_player_headers(url)
    limits = httpx.Limits(max_keepalive_connections=1, max_connections=1)
    with httpx.Client(timeout=20.0, follow_redirects=False, headers=headers, limits=limits) as client:
        r = _get_with_redirects(client, url)
        secret = _capture_hls_cookies(client, r, str(r.url)) or _hls_secret(client, str(r.url))
        if r.status_code >= 400 or not r.text.lstrip().startswith("#EXTM3U"):
            log.warning("hls playlist %s -> %s", url, r.status_code)
            return None, r.status_code in {401, 403}
        if not secret:
            log.warning("hls missing session %s", url)
            return None, True
        body = r.text
        current = _with_session(str(r.url), secret)
        for _ in range(4):
            refs = _playlist_refs(body, current, session=secret)
            if not refs:
                return None, False
            child = refs[-1]
            r = _get_with_redirects(client, child)
            secret = _capture_hls_cookies(client, r, str(r.url)) or secret
            if r.status_code >= 400:
                log.warning("hls media %s -> %s", child, r.status_code)
                return None, r.status_code in {401, 403}
            current = _with_session(str(r.url), secret)
            ctype = (r.headers.get("content-type") or "").lower()
            if "mpegurl" in ctype or r.text.lstrip().startswith("#EXTM3U"):
                body = r.text
                continue
            return r.content, False
    return None, False


def fetch_hls_segment(url: str) -> bytes | None:
    """Follow the HLS challenge and refresh rejected short-lived sessions."""
    for attempt in range(5):
        segment, retry = _fetch_hls_segment_once(url)
        if segment is not None:
            return segment
        if not retry or attempt == 4:
            break
        log.info("refreshing rejected Sentinel HLS session")
        time.sleep(0.2 * (attempt + 1))
    return None


def local_rtsp_url(sid: str) -> str | None:
    base = (settings.sentinel_local_rtsp_url or "").rstrip("/")
    if not base or not sid:
        return None
    return f"{base}/stream/{sid}"


def _is_local_rtsp(url: str) -> bool:
    base = (settings.sentinel_local_rtsp_url or "").rstrip("/")
    return bool(base) and url.startswith(base)


def _rtsp_tcp_reachable(url: str, timeout: float = 0.5) -> bool:
    parts = urlsplit(url)
    host = parts.hostname
    port = parts.port or 8554
    if not host:
        return False
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def hls_media_playlist_url(url: str) -> str | None:
    """Handshake MediaMTX HLS and return the sessioned media playlist ffmpeg can open."""
    headers = _hls_player_headers(url)
    limits = httpx.Limits(max_keepalive_connections=1, max_connections=1)
    with httpx.Client(timeout=20.0, follow_redirects=False, headers=headers, limits=limits) as client:
        r = _get_with_redirects(client, url)
        secret = _capture_hls_cookies(client, r, str(r.url)) or _hls_secret(client, str(r.url))
        if r.status_code >= 400 or not r.text.lstrip().startswith("#EXTM3U") or not secret:
            log.warning("hls playlist %s -> %s", url, r.status_code)
            return None
        current = _with_session(str(r.url), secret)
        body = r.text
        for _ in range(4):
            if "#EXT-X-STREAM-INF" not in body:
                return current
            refs = _playlist_refs(body, current, session=secret)
            if not refs:
                return None
            r = _get_with_redirects(client, refs[0])
            secret = _capture_hls_cookies(client, r, str(r.url)) or secret
            if r.status_code >= 400:
                return None
            current = _with_session(str(r.url), secret)
            body = r.text
            if "mpegurl" not in (r.headers.get("content-type") or "").lower() and not body.lstrip().startswith("#EXTM3U"):
                return current
        return current


def _stop_local_publisher() -> None:
    global _local_pub, _local_sid
    if _local_pub is not None:
        _local_pub.terminate()
        try:
            _local_pub.wait(timeout=4)
        except Exception:
            _local_pub.kill()
        _local_pub = None
    _local_sid = None


def _ensure_local_publisher(sid: str, hls_url: str) -> bool:
    """Republish catalogue HLS to internal MediaMTX so OpenCV can use RTSP over TCP."""
    global _local_pub, _local_sid
    dest = local_rtsp_url(sid)
    ffmpeg = shutil.which("ffmpeg")
    if not dest or not ffmpeg:
        return False
    if _local_pub is not None and _local_sid == sid and _local_pub.poll() is None:
        return True
    _stop_local_publisher()
    playlist = hls_media_playlist_url(hls_url)
    if not playlist:
        log.warning("cannot restream SEN-%s: HLS playlist unavailable", sid)
        return False
    player = _hls_player_headers(hls_url)
    cmd = [
        ffmpeg,
        "-hide_banner",
        "-loglevel",
        "warning",
        "-nostdin",
        "-rw_timeout",
        "8000000",
        "-user_agent",
        player["User-Agent"],
        "-headers",
        f"Referer: {player['Referer']}\r\nOrigin: {player['Origin']}\r\n",
        "-i",
        playlist,
        "-an",
        "-c:v",
        "libx264",
        "-preset",
        "ultrafast",
        "-tune",
        "zerolatency",
        "-pix_fmt",
        "yuv420p",
        "-g",
        "30",
        "-rtsp_transport",
        "tcp",
        "-f",
        "rtsp",
        dest,
    ]
    err_log = Path("/tmp/gusip-rtsp-publisher.log")
    _local_pub = subprocess.Popen(
        cmd,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=err_log.open("ab"),
    )
    _local_sid = sid
    deadline = time.monotonic() + 20.0
    while time.monotonic() < deadline:
        if _local_pub.poll() is not None:
            log.warning("local RTSP publisher exited for SEN-%s", sid)
            _stop_local_publisher()
            return False
        if _rtsp_describe_ok(dest):
            log.info("local RTSP ready rtsp://mediamtx:8554/stream/%s", sid)
            return True
        time.sleep(0.8)
    log.warning("local RTSP publisher did not become ready for SEN-%s", sid)
    _stop_local_publisher()
    return False


def _rtsp_describe_ok(url: str) -> bool:
    probe = shutil.which("ffprobe")
    if not probe:
        return False
    try:
        result = subprocess.run(
            [probe, "-v", "error", "-rtsp_transport", "tcp", "-timeout", "2000000", "-show_entries", "stream=codec_type", "-of", "csv=p=0", url],
            capture_output=True,
            timeout=6,
        )
        return result.returncode == 0 and b"video" in (result.stdout or b"")
    except Exception:
        return False


def _opencv_read_frame(url: str, timeout_s: float) -> tuple[bytes | None, float | None]:
    os.environ.setdefault("OPENCV_FFMPEG_CAPTURE_OPTIONS", "rtsp_transport;tcp")
    try:
        import cv2
    except Exception:
        return None, None
    validate_sentinel_url(url, frozenset({"rtsp"}))
    cap = None
    try:
        cap = cv2.VideoCapture(url, cv2.CAP_FFMPEG)
        for name, value in (
            ("CAP_PROP_OPEN_TIMEOUT_MSEC", 3000),
            ("CAP_PROP_READ_TIMEOUT_MSEC", int(timeout_s * 1000)),
        ):
            prop = getattr(cv2, name, None)
            if prop is not None:
                cap.set(prop, value)
        if not cap.isOpened():
            return None, None
        deadline = time.monotonic() + timeout_s
        while time.monotonic() < deadline:
            ok, frame = cap.read()
            if not ok or frame is None:
                time.sleep(0.05)
                continue
            pts_ms = float(cap.get(cv2.CAP_PROP_POS_MSEC) or 0)
            pts = pts_ms / 1000.0 if pts_ms > 0 else None
            encoded, buf = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 90])
            if encoded:
                return buf.tobytes(), pts
        return None, None
    except Exception as exc:
        log.info("opencv rtsp %s: %s (join RPS/POC is expected until IDR)", url, exc)
        return None, None
    finally:
        if cap is not None:
            cap.release()


def _opencv_read_frames(url: str, timeout_s: float, count: int = 5, skip: int = 2) -> list[tuple[bytes, float | None]]:
    """One TCP session, several real frames. Needed for low-res plate fusion."""
    os.environ.setdefault("OPENCV_FFMPEG_CAPTURE_OPTIONS", "rtsp_transport;tcp")
    try:
        import cv2
    except Exception:
        return []
    validate_sentinel_url(url, frozenset({"rtsp"}))
    cap = None
    frames: list[tuple[bytes, float | None]] = []
    try:
        cap = cv2.VideoCapture(url, cv2.CAP_FFMPEG)
        for name, value in (
            ("CAP_PROP_OPEN_TIMEOUT_MSEC", 3000),
            ("CAP_PROP_READ_TIMEOUT_MSEC", int(timeout_s * 1000)),
        ):
            prop = getattr(cv2, name, None)
            if prop is not None:
                cap.set(prop, value)
        if not cap.isOpened():
            return []
        deadline = time.monotonic() + timeout_s
        skipped = 0
        while time.monotonic() < deadline and len(frames) < count:
            ok, frame = cap.read()
            if not ok or frame is None:
                time.sleep(0.04)
                continue
            if skipped < skip:
                skipped += 1
                continue
            skipped = 0
            pts_ms = float(cap.get(cv2.CAP_PROP_POS_MSEC) or 0)
            pts = pts_ms / 1000.0 if pts_ms > 0 else None
            encoded, buf = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 90])
            if encoded:
                frames.append((buf.tobytes(), pts))
        return frames
    except Exception as exc:
        log.info("opencv burst %s: %s", url, exc)
        return frames
    finally:
        if cap is not None:
            cap.release()


def _grab_rtsp_opencv(url: str, *, timeout_s: float = 6.0) -> tuple[bytes | None, float | None]:
    """Official Sentinel Python client: OpenCV + FFmpeg backend, RTSP over TCP, PTS from CAP_PROP_POS_MSEC."""
    box: list[tuple[bytes | None, float | None]] = [(None, None)]

    def _run() -> None:
        box[0] = _opencv_read_frame(url, timeout_s)

    worker = threading.Thread(target=_run, name="sentinel-opencv", daemon=True)
    worker.start()
    worker.join(timeout_s + 2.0)
    if worker.is_alive():
        log.info("opencv rtsp still opening after %.0fs; falling back", timeout_s + 2)
        return None, None
    return box[0]


def _grab_rtsp_opencv_burst(url: str, count: int = 5, *, timeout_s: float = 10.0) -> list[tuple[bytes, float | None]]:
    box: list[list[tuple[bytes, float | None]]] = [[]]

    def _run() -> None:
        box[0] = _opencv_read_frames(url, timeout_s, count=count)

    worker = threading.Thread(target=_run, name="sentinel-opencv-burst", daemon=True)
    worker.start()
    worker.join(timeout_s + 2.0)
    if worker.is_alive():
        log.info("opencv burst still opening after %.0fs", timeout_s + 2)
        return []
    return box[0]


def _grab_frame_burst(url: str, count: int = 5) -> list[tuple[bytes, float | None]]:
    if url.startswith("rtsp://"):
        burst = _grab_rtsp_opencv_burst(url, count=count)
        if burst:
            return burst
    jpeg, pts = _grab_frame_sample(url)
    return [(jpeg, pts)] if jpeg else []


def _grab_ffmpeg(url: str, src: str, ffmpeg: str) -> tuple[bytes | None, float | None]:
    cmd = grab_cmd(src, ffmpeg)
    try:
        proc = subprocess.run(cmd, capture_output=True, timeout=20)
    except subprocess.TimeoutExpired:
        _report_feed(logging.WARNING, "", url, "ffmpeg", "timeout")
        if url.startswith("rtsp://"):
            delay = _mark_rtsp_failure()
            log.info("RTSP retry delayed %.0fs; ANPR will use HLS", delay)
        return None, None
    err = (proc.stderr or b"").decode("utf-8", "replace")
    pts = _parse_progress_pts(err)
    if _is_join_decoder_warning(err):
        log.info("decoder warming on join (expected until IDR) %s", url)
    if proc.stdout and proc.stdout[:2] == b"\xff\xd8":
        if url.startswith("rtsp://"):
            _mark_rtsp_success()
        return proc.stdout, pts
    if url.startswith("rtsp://") and ("Connection timed out" in err or "Connection refused" in err):
        delay = _mark_rtsp_failure()
        log.info("RTSP :8554 unreachable; retrying in %.0fs while ANPR uses HLS", delay)
    elif proc.returncode != 0:
        _report_feed(logging.WARNING, "", url, "ffmpeg", err[-400:] or f"exit {proc.returncode}")
    return None, pts


def _grab_frame_sample(url: str, offset: float | None = None) -> tuple[bytes | None, float | None]:
    # offset is ignored: live RTP has no seeking (integrator guide §1 / §3).
    _ = offset
    if url.startswith("rtsp://"):
        local = _is_local_rtsp(url)
        if not local:
            if not _rtsp_available():
                return None, None
            if not _rtsp_tcp_reachable(url):
                delay = _mark_rtsp_failure()
                log.info("RTSP :8554 unreachable; retrying in %.0fs while using local RTSP/HLS", delay)
                return None, None
        jpeg, pts = _grab_rtsp_opencv(url)
        if jpeg:
            if not local:
                _mark_rtsp_success()
            return jpeg, pts
        if local:
            return None, None
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        log.warning("ffmpeg not installed — cannot sample Sentinel frames")
        return None, None
    tmp_path: str | None = None
    src = url
    if url.startswith("http"):
        segment = fetch_hls_segment(url)
        if not segment:
            return None, None
        tmp = tempfile.NamedTemporaryFile(suffix=".bin", delete=False)
        tmp.write(segment)
        tmp.close()
        tmp_path = tmp.name
        src = tmp_path
    try:
        return _grab_ffmpeg(url, src, ffmpeg)
    finally:
        if tmp_path:
            Path(tmp_path).unlink(missing_ok=True)


def grab_frame(url: str, offset: float | None = None) -> bytes | None:
    frame, _pts = _grab_frame_sample(url, offset)
    return frame


def ocr_image(
    jpeg: bytes,
    extra_crops: list[Image.Image] | None = None,
    *,
    frames: list[bytes] | None = None,
    dets: list[dict[str, Any]] | None = None,
    camera_key: str = "",
) -> str:
    return read_plate_text(jpeg, extra_crops, frames=frames, dets=dets, camera_key=camera_key)


def vehicle_plate_crops(jpeg: bytes, dets: list[dict[str, Any]]) -> list[Image.Image]:
    return plate_crops(jpeg, dets)


async def sample_camera(cam: Camera) -> int:
    extra = dict(cam.extra or {})
    sid = str(extra.get("sentinel_id") or "")
    if extra.get("live") is False:
        return -1
    urls = inference_urls(extra)
    hls = extra.get("hls_url")
    local = local_rtsp_url(sid)
    if local and isinstance(hls, str) and hls:
        ready = await asyncio.to_thread(_ensure_local_publisher, sid, hls)
        if ready:
            urls = [local, *[u for u in urls if u != extra.get("rtsp_url")]]
        else:
            urls = [u for u in urls if not str(u).startswith("rtsp://") or _is_local_rtsp(str(u))] or urls
    if not sid or not urls:
        return -1
    jpeg = None
    pts = None
    dets: list[dict[str, Any]] = []
    url = urls[0]
    burst: list[tuple[bytes, float | None]] = []
    for candidate in urls:
        burst = await asyncio.to_thread(_grab_frame_burst, candidate, 5)
        if burst:
            url = candidate
            jpeg, pts = burst[-1]
            break
        jpeg, pts = await asyncio.to_thread(_grab_frame_sample, candidate)
        if jpeg:
            url = candidate
            burst = [(jpeg, pts)]
            break
        _report_feed(logging.WARNING, sid, candidate, "opencv+ffmpeg", "no frame — reconnect with backoff")
    if not jpeg:
        return -1
    clock_extra = dict(extra)
    event_timestamp, stream_epoch = advance_stream_clock(clock_extra, pts)
    PREVIEW_DIR.mkdir(parents=True, exist_ok=True)
    (PREVIEW_DIR / f"{cam.code}.jpg").write_bytes(jpeg)
    try:
        from app.workers.inference import detect_jpeg, emit_detections, inference_available

        if inference_available():
            dets = await asyncio.to_thread(
                detect_jpeg, jpeg, camera_key=cam.code, stream_epoch=stream_epoch
            )
            if dets:
                await emit_detections(
                    cam,
                    dets,
                    jpeg,
                    timestamp=event_timestamp,
                    stream_epoch=stream_epoch,
                    stream_pts=pts,
                )
                log.info("YOLO live %s objects=%s", cam.code, len(dets))
    except Exception:
        log.exception("YOLO on %s failed", cam.code)
    frames = [frame for frame, _pts in burst if frame]
    text = await asyncio.to_thread(
        ocr_image,
        jpeg,
        None,
        frames=frames,
        dets=dets,
        camera_key=cam.code,
    )
    plates = extract_plates(text)
    emitted = 0
    async with SessionLocal() as db:
        fresh = await db.get(Camera, cam.id)
        if not fresh:
            return 0
        extra = dict(fresh.extra or {})
        for key in ("stream_epoch", "stream_base_pts", "stream_base_time", "stream_last_pts"):
            if key in clock_extra:
                extra[key] = clock_extra[key]
        extra["last_ocr"] = text[:400]
        extra["anpr_burst"] = len(frames)
        extra["last_sample_at"] = event_timestamp.isoformat()
        extra["last_grab_url"] = url
        extra["preview_url"] = f"/api/v1/feeds/sentinel/{sid}/preview"
        fresh.extra = extra
        flag_modified(fresh, "extra")
        fresh.last_seen_at = datetime.now(timezone.utc)
        fresh.status = "online"
        await db.commit()

        if not plates:
            return 0

        for plate, conf in plates:
            png = jpeg
            try:
                from io import BytesIO

                im = Image.open(BytesIO(jpeg)).convert("RGB")
                buf = BytesIO()
                im.save(buf, format="PNG")
                png = buf.getvalue()
            except Exception:
                png = jpeg
            snap = save_snapshot_png(png, prefix=f"anpr-{cam.code}")
            await ingest_detection(
                db,
                {
                    "camera_id": cam.id,
                    "event_type": "anpr",
                    "object_type": "vehicle",
                    "timestamp": event_timestamp,
                    "plate_number": plate,
                    "confidence": conf,
                    "snapshot_url": snap,
                    "attributes": {
                        "source_type": "sentinel",
                        "official_location": extra.get("official_location"),
                        "ocr": text[:200],
                        "grab": "rtsp" if str(url).startswith("rtsp://") else "hls",
                        "codec": extra.get("codec"),
                        "stream_pts": pts,
                        "stream_epoch": stream_epoch,
                    },
                },
            )
            emitted += 1
            log.info("ANPR %s -> %s", cam.code, plate)
    return emitted


async def sync_loop() -> None:
    while True:
        try:
            await sync_catalog()
        except Exception:
            log.exception("sentinel catalog sync failed")
        await asyncio.sleep(120)


async def anpr_loop() -> None:
    idx = 0
    fail_streak = 0
    while True:
        grabbed = False
        had_cams = False
        try:
            async with SessionLocal() as db:
                cams = list(
                    (
                        await db.execute(
                            select(Camera).where(
                                Camera.source_type == "sentinel",
                                Camera.is_active.is_(True),
                                Camera.status == "online",
                            )
                        )
                    ).scalars()
                )
            if cams:
                had_cams = True
                cam = cams[idx % len(cams)]
                idx += 1
                n = await sample_camera(cam)
                grabbed = n >= 0
                log.info(
                    "sampled %s plates=%s (%s/%s)",
                    cam.code,
                    max(n, 0),
                    (idx % len(cams)) or len(cams),
                    len(cams),
                )
        except Exception:
            log.exception("sentinel ANPR loop failed")
        if not had_cams:
            fail_streak = 0
            delay = settings.sentinel_anpr_interval_s
        elif grabbed:
            fail_streak = 0
            delay = settings.sentinel_anpr_interval_s
        else:
            fail_streak += 1
            delay = min(30.0, 2.0 * (2 ** (fail_streak - 1)))
        await asyncio.sleep(delay)

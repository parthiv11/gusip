"""Official Sentinel sandbox adapter.

Contract: https://sentinel.gujarat.gov.in/resource
Catalogue is /api/ingest. Inference uses RTSP over TCP. The HTTP /stream/<id>
range endpoint is a browser fallback only — never the ANPR/YOLO path.
"""

from __future__ import annotations

import asyncio
import logging
import shutil
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlencode, urljoin, urlparse, urlsplit, urlunsplit

import httpx
from geoalchemy2.elements import WKTElement
from PIL import Image, ImageEnhance, ImageFilter, ImageOps
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from app.config import get_settings
from app.db import SessionLocal
from app.models.camera import Camera, Department
from app.services.anpr import extract_plates
from app.services.pipeline import ingest_detection
from app.services.storage import DATA_DIR, save_snapshot_png
from app.workers.sentinel_geo import geocode

log = logging.getLogger("gusip.sentinel")
settings = get_settings()
PREVIEW_DIR = DATA_DIR / "previews"
_rtsp_blocked = False
SENTINEL_HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; GUSIP/1.0; Sentinel ingest)",
    "Accept": "application/json, */*",
    "Referer": "https://sentinel.gujarat.gov.in/resource",
}


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
    host = urlparse(base).hostname or "live.sentinelgujarat.in"
    hls = item.get("hls_live_url") or item.get("hls_url")
    whep = item.get("webrtc_url") or item.get("whep_url")
    rtsp = item.get("rtsp_url")
    if not rtsp and sid:
        rtsp = f"rtsp://{host}:8554/stream/{sid}"
    live = _is_live(item)

    def abs_http(url: str | None) -> str | None:
        if not url:
            return None
        if url.startswith("http") or url.startswith("rtsp://"):
            return url
        return f"{base}{url}"

    return {
        "id": sid,
        "name": item.get("name") or f"Sentinel {sid}",
        "location": item.get("location") or item.get("name") or f"SEN-{sid}",
        "codec": item.get("codec") or "",
        "live": live,
        "width": int(item.get("width") or 0),
        "height": int(item.get("height") or 0),
        "fps": float(item.get("fps") or 0),
        "bitrate_kbps": item.get("bitrate_kbps") or 0,
        "rtsp_url": rtsp,
        "whep_url": abs_http(whep),
        "hls_url": abs_http(hls),
        "stream_url": abs_http(f"/stream/{sid}") if sid else None,
        "container": item.get("container"),
        "status": "live" if live else str(item.get("status") or "offline"),
    }


def inference_urls(extra: dict[str, Any] | None) -> list[str]:
    """RTSP first (AI path). HLS if port 8554 is blocked. Never HTTP /stream."""
    extra = extra or {}
    urls: list[str] = []
    for key in ("rtsp_url", "hls_url"):
        u = extra.get(key)
        if isinstance(u, str) and u and u not in urls:
            urls.append(u)
    return urls


def inference_url(extra: dict[str, Any] | None) -> str | None:
    urls = inference_urls(extra)
    return urls[0] if urls else None


def grab_cmd(url: str, ffmpeg: str = "ffmpeg") -> list[str]:
    cmd = [ffmpeg, "-hide_banner", "-loglevel", "error"]
    if url.startswith("rtsp://"):
        cmd += ["-rtsp_transport", "tcp", "-timeout", "3000000"]
    else:
        # Cloudflare 403s HLS without a browser UA (integrator HLS path on :443).
        cmd += [
            "-rw_timeout",
            "8000000",
            "-user_agent",
            "Mozilla/5.0 GUSIP-ANPR",
            "-headers",
            "Referer: https://live.sentinelgujarat.in/\r\n",
        ]
    cmd += [
        "-i",
        url,
        "-frames:v",
        "1",
        "-an",
        "-c:v",
        "mjpeg",
        "-vf",
        "scale=1280:-2",
        "-q:v",
        "3",
        "-f",
        "image2",
        "pipe:1",
    ]
    return cmd


async def fetch_catalog() -> list[dict[str, Any]]:
    base = settings.sentinel_base_url.rstrip("/")
    async with httpx.AsyncClient(timeout=30.0, follow_redirects=True, headers=SENTINEL_HEADERS) as client:
        for path in ("/api/ingest", "/api/cameras"):
            try:
                r = await client.get(f"{base}{path}")
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
    async with httpx.AsyncClient(timeout=20.0, follow_redirects=True, headers=SENTINEL_HEADERS) as client:
        r = await client.get(f"{settings.sentinel_base_url.rstrip('/')}/api/cameras/{cam_id}/state")
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


def _playlist_refs(body: str, base: str) -> list[str]:
    parent = urlsplit(base)
    parent_q = dict(parse_qsl(parent.query))
    refs: list[str] = []
    for line in body.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        child = urlsplit(urljoin(base, line))
        q = {**parent_q, **dict(parse_qsl(child.query))}
        refs.append(urlunsplit((child.scheme, child.netloc, child.path, urlencode(q), child.fragment)))
    return refs


def fetch_hls_segment(url: str) -> bytes | None:
    """Follow Cloudflare cookieCheck, then pull the latest media segment."""
    headers = {**SENTINEL_HEADERS, "Accept": "*/*"}
    with httpx.Client(timeout=20.0, follow_redirects=True, headers=headers) as client:
        r = client.get(url)
        if r.status_code >= 400 or not r.text.lstrip().startswith("#EXTM3U"):
            log.warning("hls playlist %s -> %s", url, r.status_code)
            return None
        ck = client.cookies.get("cookieCheck")
        sess = client.cookies.get("hlsSession")
        if not sess:
            log.warning("hls missing session cookie %s", url)
            return None
        cookie_hdr = f"cookieCheck={ck}; hlsSession={sess}"
        body = r.text
        current = str(r.url)
        for _ in range(4):
            refs = _playlist_refs(body, current)
            if not refs:
                return None
            r = client.get(refs[-1], headers={"Cookie": cookie_hdr})
            if r.status_code >= 400:
                log.warning("hls media %s -> %s", refs[-1], r.status_code)
                return None
            current = str(r.url)
            ctype = (r.headers.get("content-type") or "").lower()
            if "mpegurl" in ctype or r.text.lstrip().startswith("#EXTM3U"):
                body = r.text
                continue
            return r.content
    return None


def grab_frame(url: str, offset: float | None = None) -> bytes | None:
    # offset is ignored: live RTP has no seeking (integrator guide §1 / §3).
    global _rtsp_blocked
    _ = offset
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        log.warning("ffmpeg not installed — cannot sample Sentinel frames")
        return None
    if url.startswith("rtsp://") and _rtsp_blocked:
        return None
    tmp_path: str | None = None
    src = url
    if url.startswith("http"):
        segment = fetch_hls_segment(url)
        if not segment:
            return None
        tmp = tempfile.NamedTemporaryFile(suffix=".bin", delete=False)
        tmp.write(segment)
        tmp.close()
        tmp_path = tmp.name
        src = tmp_path
    cmd = grab_cmd(src, ffmpeg)
    try:
        proc = subprocess.run(cmd, capture_output=True, timeout=20)
    except subprocess.TimeoutExpired:
        log.warning("ffmpeg timeout %s", url)
        if url.startswith("rtsp://"):
            _rtsp_blocked = True
        return None
    finally:
        if tmp_path:
            Path(tmp_path).unlink(missing_ok=True)
    err = (proc.stderr or b"").decode("utf-8", "replace")
    if "Error constructing the frame RPS" in err or "Could not find ref with POC" in err:
        log.info("decoder warming on join (expected until IDR) %s", url)
    if proc.stdout and proc.stdout[:2] == b"\xff\xd8":
        return proc.stdout
    if url.startswith("rtsp://") and ("Connection timed out" in err or "Connection refused" in err):
        _rtsp_blocked = True
        log.info("RTSP :8554 unreachable from this host — ANPR will use HLS")
    if proc.returncode != 0:
        log.warning("ffmpeg failed %s: %s", url, err[-400:])
    return None


def ocr_image(jpeg: bytes) -> str:
    try:
        import pytesseract
    except Exception:
        return ""
    PREVIEW_DIR.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(suffix=".jpg") as tmp:
        tmp.write(jpeg)
        tmp.flush()
        img = Image.open(tmp.name).convert("L")
        img = ImageOps.autocontrast(img)
        img = ImageEnhance.Contrast(img).enhance(1.8)
        img = img.filter(ImageFilter.SHARPEN)
        w, h = img.size
        crops = [img, img.crop((0, int(h * 0.45), w, h)), img.crop((int(w * 0.2), int(h * 0.35), int(w * 0.8), h))]
        texts = []
        for crop in crops:
            big = crop.resize((crop.width * 2, crop.height * 2))
            texts.append(
                pytesseract.image_to_string(
                    big,
                    config="--oem 1 --psm 11 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789",
                )
            )
        return " ".join(texts)


async def sample_camera(cam: Camera) -> int:
    extra = dict(cam.extra or {})
    sid = str(extra.get("sentinel_id") or "")
    urls = inference_urls(extra)
    if not sid or not urls:
        return -1
    jpeg = None
    url = urls[0]
    for candidate in urls:
        jpeg = await asyncio.to_thread(grab_frame, candidate)
        if jpeg:
            url = candidate
            break
    if not jpeg:
        return -1
    PREVIEW_DIR.mkdir(parents=True, exist_ok=True)
    (PREVIEW_DIR / f"{cam.code}.jpg").write_bytes(jpeg)
    try:
        from app.workers.inference import detect_jpeg, emit_detections, inference_available

        if inference_available():
            dets = await asyncio.to_thread(detect_jpeg, jpeg)
            if dets:
                await emit_detections(cam, dets, jpeg)
                log.info("YOLO live %s objects=%s", cam.code, len(dets))
    except Exception:
        log.exception("YOLO on %s failed", cam.code)
    text = await asyncio.to_thread(ocr_image, jpeg)
    plates = extract_plates(text)
    emitted = 0
    async with SessionLocal() as db:
        fresh = await db.get(Camera, cam.id)
        if not fresh:
            return 0
        extra = dict(fresh.extra or {})
        extra["last_ocr"] = text[:400]
        extra["last_sample_at"] = datetime.now(timezone.utc).isoformat()
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
                    "plate_number": plate,
                    "confidence": conf,
                    "snapshot_url": snap,
                    "attributes": {
                        "source_type": "sentinel",
                        "official_location": extra.get("official_location"),
                        "ocr": text[:200],
                        "grab": "rtsp" if str(url).startswith("rtsp://") else "hls",
                        "codec": extra.get("codec"),
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

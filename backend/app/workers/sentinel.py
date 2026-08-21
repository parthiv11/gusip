"""Official Gujarat Police evaluation feed adapter — live.sentinelgujarat.in."""

from __future__ import annotations

import asyncio
import logging
import shutil
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx
from geoalchemy2.elements import WKTElement
from PIL import Image, ImageEnhance, ImageFilter, ImageOps
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

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


def _abs(url: str | None) -> str | None:
    if not url:
        return None
    if url.startswith("http"):
        return url
    return f"{settings.sentinel_base_url.rstrip('/')}{url}"


async def fetch_catalog() -> list[dict[str, Any]]:
    async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
        r = await client.get(f"{settings.sentinel_base_url.rstrip('/')}/api/cameras")
        r.raise_for_status()
        return list(r.json().get("cameras") or [])


async def fetch_state(cam_id: str) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=20.0, follow_redirects=True) as client:
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
            for c in (
                await db.execute(select(Camera).where(Camera.source_type == "sentinel"))
            ).scalars()
        }
        seen: set[str] = set()
        for item in cams:
            sid = str(item.get("id"))
            code = f"SEN-{sid}"
            seen.add(code)
            loc = item.get("location") or item.get("name") or code
            lat, lon, city = geocode(loc)
            status = "online" if item.get("status") == "live" else "offline"
            extra = {
                "sentinel_id": sid,
                "stream_url": _abs(f"/stream/{sid}"),
                "hls_url": _abs(item.get("hls_url")) if item.get("hls_url") else None,
                "codec": item.get("codec"),
                "container": item.get("container"),
                "delivery": item.get("delivery"),
                "official_location": loc,
                "portal": settings.sentinel_base_url,
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
                from sqlalchemy.orm.attributes import flag_modified

                flag_modified(cam, "extra")
                cam.is_active = True
            else:
                db.add(
                    Camera(
                        code=code,
                        name=item.get("name") or f"Sentinel {sid}",
                        department_id=dept.id,
                        camera_type="ip" if item.get("container") != "avi" else "analog",
                        ownership="Gujarat Police / SCRB evaluation",
                        source_type="sentinel",
                        vendor="Sentinel live-feed simulator",
                        vendor_api_ref=f"sentinel:{sid}",
                        status=status,
                        connectivity="evaluation-portal",
                        storage_details="Source remains on live.sentinelgujarat.in (not centralised)",
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


def grab_frame(stream_url: str, offset: float | None) -> bytes | None:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        log.warning("ffmpeg not installed — cannot sample Sentinel frames")
        return None
    ss = max(0.0, float(offset or 0))
    cmd = [
        ffmpeg,
        "-hide_banner",
        "-loglevel",
        "error",
        "-user_agent",
        "GUSIP-Sentinel-Adapter/1.0",
        "-ss",
        f"{ss:.3f}",
        "-i",
        stream_url,
        "-frames:v",
        "1",
        "-vf",
        "scale=1280:-2",
        "-q:v",
        "3",
        "-f",
        "image2",
        "pipe:1",
    ]
    try:
        proc = subprocess.run(cmd, capture_output=True, timeout=25)
    except subprocess.TimeoutExpired:
        log.warning("ffmpeg timeout %s", stream_url)
        return None
    if proc.returncode != 0 or not proc.stdout:
        log.debug("ffmpeg failed: %s", proc.stderr[-300:] if proc.stderr else "")
        return None
    return proc.stdout


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
    sid = str((cam.extra or {}).get("sentinel_id") or "")
    if not sid:
        return 0
    try:
        state = await fetch_state(sid)
    except Exception:
        log.exception("state fetch failed %s", cam.code)
        return 0
    stream = _abs(state.get("stream_url") or f"/stream/{sid}")
    if not stream:
        return 0
    offset = state.get("slot_offset") or state.get("offset") or 0
    jpeg = await asyncio.to_thread(grab_frame, stream, offset)
    if not jpeg:
        return 0
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
        extra["preview_url"] = f"/api/v1/feeds/sentinel/{sid}/preview"
        fresh.extra = extra
        from sqlalchemy.orm.attributes import flag_modified

        flag_modified(fresh, "extra")
        fresh.last_seen_at = datetime.now(timezone.utc)
        fresh.status = "online" if state.get("status") == "live" else "offline"
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
                        "container": extra.get("container"),
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
    while True:
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
                cam = cams[idx % len(cams)]
                idx += 1
                n = await sample_camera(cam)
                log.info("sampled %s plates=%s (%s/%s)", cam.code, n, (idx % len(cams)) or len(cams), len(cams))
        except Exception:
            log.exception("sentinel ANPR loop failed")
        await asyncio.sleep(settings.sentinel_anpr_interval_s)

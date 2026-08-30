"""Grab live Sentinel frames and run YOLO/OCR without touching the event bus."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

from sqlalchemy import select

from app.db import SessionLocal
from app.models.camera import Camera
from app.services.anpr import extract_plates
from app.workers.inference import detect_jpeg, inference_available
from app.workers.sentinel import (
    PREVIEW_DIR,
    _ensure_local_publisher,
    _grab_frame_burst,
    _grab_frame_sample,
    inference_urls,
    local_rtsp_url,
    ocr_image,
    vehicle_plate_crops,
)


async def grab_one(cam: Camera) -> dict:
    extra = dict(cam.extra or {})
    sid = str(extra.get("sentinel_id") or "")
    hls = extra.get("hls_url")
    local = local_rtsp_url(sid)
    urls = inference_urls(extra)
    if local and isinstance(hls, str) and hls:
        if await asyncio.to_thread(_ensure_local_publisher, sid, hls):
            urls = [local]
    jpeg: bytes | None = b""
    pts = None
    src = ""
    burst: list[tuple[bytes, float | None]] = []
    for url in urls:
        burst = await asyncio.to_thread(_grab_frame_burst, url, 5)
        if burst:
            jpeg, pts = burst[-1]
            src = url
            break
        jpeg, pts = await asyncio.to_thread(_grab_frame_sample, url)
        if jpeg:
            src = url
            burst = [(jpeg, pts)]
            break
    jpeg = jpeg or b""
    if not jpeg:
        return {
            "code": cam.code,
            "name": cam.name,
            "address": cam.address,
            "src": "",
            "bytes": 0,
            "pts": pts,
            "objects": [],
            "ocr_preview": "",
            "plates": [],
            "plate_crops": 0,
            "error": "no frame",
        }
    PREVIEW_DIR.mkdir(parents=True, exist_ok=True)
    (PREVIEW_DIR / f"{cam.code}.jpg").write_bytes(jpeg)
    dets = detect_jpeg(jpeg, camera_key=cam.code)
    from app.services.plate_ocr import detect_plate_boxes

    boxes = await asyncio.to_thread(detect_plate_boxes, jpeg, dets)
    frames = [frame for frame, _pts in burst if frame]
    crops = await asyncio.to_thread(vehicle_plate_crops, jpeg, dets)
    text = await asyncio.to_thread(
        ocr_image, jpeg, None, frames=frames, dets=dets, camera_key=cam.code
    )
    plates = extract_plates(text)
    return {
        "code": cam.code,
        "name": cam.name,
        "address": cam.address,
        "src": src,
        "bytes": len(jpeg),
        "pts": pts,
        "objects": [
            {
                "t": det.get("object_type"),
                "cls": det.get("class_name"),
                "conf": round(float(det.get("confidence") or 0), 3),
            }
            for det in dets[:12]
        ],
        "plate_boxes": len(boxes),
        "plate_crops": len(crops),
        "burst": len(frames),
        "ocr_preview": " ".join(text.split())[:180],
        "plates": plates,
    }


async def main() -> None:
    print("yolo_available", inference_available())
    async with SessionLocal() as db:
        cams = list(
            (
                await db.execute(
                    select(Camera).where(
                        Camera.source_type == "sentinel",
                        Camera.is_active.is_(True),
                    )
                )
            ).scalars()
        )
    prefer = ["SEN-1", "SEN-4", "SEN-14", "SEN-29", "SEN-2", "SEN-13"]
    by_code = {cam.code: cam for cam in cams}
    picked = [by_code[code] for code in prefer if code in by_code]
    results = []
    for cam in picked:
        row = await grab_one(cam)
        results.append(row)
        print(json.dumps(row))
    Path("/tmp/gusip-frame-check.json").write_text(json.dumps(results, indent=2))


if __name__ == "__main__":
    asyncio.run(main())

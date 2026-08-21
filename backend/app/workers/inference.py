"""YOLOv8 detection on official Sentinel frames. Falls back to simulate if unset/unavailable."""

from __future__ import annotations

import asyncio
import logging
from io import BytesIO
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image
from sqlalchemy import select

from app.config import get_settings
from app.db import SessionLocal
from app.models.camera import Camera
from app.services.pipeline import ingest_detection
from app.services.storage import DATA_DIR

log = logging.getLogger("gusip.yolo")
settings = get_settings()

_model: Any = None
PREVIEW_DIR = DATA_DIR / "previews"

# person, bicycle, car, motorcycle, bus, truck
YOLO_CLASSES = [0, 1, 2, 3, 5, 7]


def inference_available() -> bool:
    try:
        import ultralytics  # noqa: F401

        return True
    except Exception:
        return settings.inference_mode == "yolo"


def get_model() -> Any:
    global _model
    if _model is None:
        from ultralytics import YOLO

        _model = YOLO("yolov8n.pt")
        log.info("YOLOv8n loaded device=cpu")
    return _model


def warmup() -> bool:
    if not inference_available():
        log.warning("YOLO not available (mode=%s)", settings.inference_mode)
        return False
    get_model()
    return True


def detect_frame(frame) -> list[dict[str, Any]]:
    """Run YOLOv8n. Bboxes are scaled to 400×240 so the control-room overlay matches."""
    if not inference_available():
        return []
    model = get_model()
    results = model.predict(frame, classes=YOLO_CLASSES, verbose=False, device="cpu", imgsz=640)
    detections: list[dict[str, Any]] = []
    for r in results:
        if r.boxes is None:
            continue
        h, w = int(r.orig_shape[0]), int(r.orig_shape[1])
        for b in r.boxes:
            cls = int(b.cls[0])
            name = r.names.get(cls, "object")
            mapped = "person" if name == "person" else "two-wheeler" if name in ("motorcycle", "bicycle") else "vehicle"
            xyxy = b.xyxy[0].tolist()
            detections.append(
                {
                    "object_type": mapped,
                    "confidence": float(b.conf[0]),
                    "local_track_id": str(int(b.id[0])) if b.id is not None else None,
                    "bbox": {
                        "x": int(xyxy[0] / w * 400),
                        "y": int(xyxy[1] / h * 240),
                        "w": int((xyxy[2] - xyxy[0]) / w * 400),
                        "h": int((xyxy[3] - xyxy[1]) / h * 240),
                    },
                    "class_name": name,
                }
            )
    return detections


def detect_jpeg(jpeg: bytes) -> list[dict[str, Any]]:
    img = np.array(Image.open(BytesIO(jpeg)).convert("RGB"))
    return detect_frame(img)


async def emit_detections(cam: Camera, dets: list[dict[str, Any]], jpeg: bytes | None = None) -> int:
    if not dets:
        return 0
    snap_url = None
    if jpeg:
        try:
            from app.services.storage import save_snapshot_png

            im = Image.open(BytesIO(jpeg)).convert("RGB")
            buf = BytesIO()
            im.save(buf, format="PNG")
            snap_url = save_snapshot_png(buf.getvalue(), prefix=f"yolo-{cam.code}")
        except Exception:
            snap_url = None
    n = 0
    async with SessionLocal() as db:
        for d in dets:
            await ingest_detection(
                db,
                {
                    "camera_id": cam.id,
                    "event_type": "detection",
                    "object_type": d["object_type"],
                    "confidence": d["confidence"],
                    "local_track_id": d.get("local_track_id"),
                    "bbox": d.get("bbox") or {},
                    "snapshot_url": snap_url,
                    "attributes": {
                        "source_type": cam.source_type,
                        "model": "yolov8n",
                        "class_name": d.get("class_name"),
                    },
                },
            )
            n += 1
    return n


async def yolo_preview_loop() -> None:
    """Run YOLO on the latest Sentinel JPEG previews so Gov feeds get live boxes."""
    await asyncio.to_thread(warmup)
    idx = 0
    while True:
        try:
            files = sorted(PREVIEW_DIR.glob("SEN-*.jpg")) if PREVIEW_DIR.exists() else []
            if not files:
                await asyncio.sleep(8)
                continue
            path: Path = files[idx % len(files)]
            idx += 1
            code = path.stem
            jpeg = path.read_bytes()
            dets = await asyncio.to_thread(detect_jpeg, jpeg)
            async with SessionLocal() as db:
                cam = (await db.execute(select(Camera).where(Camera.code == code))).scalar_one_or_none()
            if cam and dets:
                n = await emit_detections(cam, dets, jpeg)
                log.info("YOLO %s objects=%s %s", code, n, [d["class_name"] for d in dets[:6]])
            else:
                log.info("YOLO %s objects=0", code)
        except Exception:
            log.exception("YOLO preview loop failed")
        await asyncio.sleep(6)

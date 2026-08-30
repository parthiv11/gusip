"""YOLOv8 detection on official Sentinel frames. Falls back to simulate if unset/unavailable."""

from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime
from io import BytesIO
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image
from sqlalchemy import select

from app.config import get_settings
from app.db import SessionLocal
from app.models.camera import Camera
from app.services.byte_track import tracker_for
from app.services.pipeline import ingest_detection
from app.services.storage import DATA_DIR

log = logging.getLogger("gusip.yolo")
settings = get_settings()

_model: Any = None
PREVIEW_DIR = DATA_DIR / "previews"
_last_face_at: dict[str, float] = {}
FACE_EVERY_S = 8.0

# person, bicycle, car, motorcycle, bus, truck
YOLO_CLASSES = [0, 1, 2, 3, 5, 7]


def inference_available() -> bool:
    if settings.inference_mode != "yolo":
        return False
    try:
        from ultralytics import YOLO  # noqa: F401

        return True
    except Exception:
        return False


def get_model() -> Any:
    global _model
    if _model is None:
        from ultralytics import YOLO

        model_path = Path(settings.inference_model_path)
        model_path.parent.mkdir(parents=True, exist_ok=True)
        _model = YOLO(str(model_path))
        log.info("YOLOv8n loaded device=cpu")
    return _model


def warmup() -> bool:
    if not inference_available():
        log.warning("YOLO not available (mode=%s)", settings.inference_mode)
        return False
    get_model()
    return True


def detect_frame(frame, *, camera_key: str | None = None, stream_epoch: int | None = None) -> list[dict[str, Any]]:
    """Run YOLOv8n and associate stable local IDs with a per-camera ByteTrack-style tracker."""
    if not inference_available():
        return []
    model = get_model()
    results = model.predict(frame, classes=YOLO_CLASSES, verbose=False, device="cpu", imgsz=960)
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
                    "x1": float(xyxy[0]),
                    "y1": float(xyxy[1]),
                    "x2": float(xyxy[2]),
                    "y2": float(xyxy[3]),
                    "frame_w": w,
                    "frame_h": h,
                    "bbox": {
                        "x": int(xyxy[0] / w * 400),
                        "y": int(xyxy[1] / h * 240),
                        "w": int((xyxy[2] - xyxy[0]) / w * 400),
                        "h": int((xyxy[3] - xyxy[1]) / h * 240),
                    },
                    "class_name": name,
                }
            )
    if camera_key:
        tracker_for(camera_key, stream_epoch).update(detections)
    return detections


def detect_jpeg(
    jpeg: bytes, *, camera_key: str | None = None, stream_epoch: int | None = None
) -> list[dict[str, Any]]:
    img = np.array(Image.open(BytesIO(jpeg)).convert("RGB"))
    return detect_frame(img, camera_key=camera_key, stream_epoch=stream_epoch)


async def emit_detections(
    cam: Camera,
    dets: list[dict[str, Any]],
    jpeg: bytes | None = None,
    *,
    timestamp: datetime | None = None,
    stream_epoch: int | None = None,
    stream_pts: float | None = None,
) -> int:
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
            attrs: dict[str, Any] = {
                "source_type": cam.source_type,
                "model": "yolov8n",
                "class_name": d.get("class_name"),
                "stream_epoch": stream_epoch,
                "stream_pts": stream_pts,
            }
            embedding = None
            this_snap = snap_url
            if d.get("object_type") == "person" and jpeg:
                face = _maybe_embed_person(cam, d, jpeg)
                if face:
                    embedding, this_snap, extra = face
                    attrs.update(extra)
            await ingest_detection(
                db,
                {
                    "camera_id": cam.id,
                    "event_type": "detection",
                    "object_type": d["object_type"],
                    "timestamp": timestamp,
                    "confidence": d["confidence"],
                    "local_track_id": d.get("local_track_id"),
                    "bbox": d.get("bbox") or {},
                    "snapshot_url": this_snap,
                    "embedding": embedding,
                    "attributes": attrs,
                },
            )
            n += 1
    return n


def _maybe_embed_person(cam: Camera, det: dict[str, Any], jpeg: bytes) -> tuple[list[float], str | None, dict[str, Any]] | None:
    from app.services.face import (
        FaceEngineError,
        arcface_ready,
        crop_quality_ok,
        embed_person_in_frame,
        person_crop,
        should_run_live_face,
    )
    from app.services.storage import save_snapshot_png

    if not should_run_live_face(cam.source_type) or not arcface_ready():
        return None
    key = f"{cam.id}:{det.get('local_track_id') or 'loose'}"
    now = time.monotonic()
    if now - _last_face_at.get(key, 0.0) < FACE_EVERY_S:
        return None
    crop = person_crop(jpeg, det)
    if crop is None:
        return None
    ok, q = crop_quality_ok(crop)
    if not ok:
        return None
    try:
        hit = embed_person_in_frame(jpeg, det)
    except FaceEngineError:
        return None
    if not hit:
        return None
    _last_face_at[key] = now
    vec, meta = hit
    png = BytesIO()
    crop.save(png, format="PNG")
    face_url = save_snapshot_png(png.getvalue(), prefix=f"face-{cam.code}")
    return vec, face_url, {
        "face_engine": meta.get("engine"),
        "face_model": meta.get("model"),
        "face_quality": q,
        "det_score": meta.get("det_score"),
        "faces": meta.get("faces"),
    }


async def yolo_preview_loop() -> None:
    """Run YOLO on the latest Sentinel JPEG previews so Gov feeds get live boxes."""
    try:
        ok = await asyncio.to_thread(warmup)
        if not ok:
            return
    except Exception:
        log.exception("YOLO warmup failed — Sentinel ingest/ANPR continues without boxes")
        return
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
            dets = await asyncio.to_thread(detect_jpeg, jpeg, camera_key=code)
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

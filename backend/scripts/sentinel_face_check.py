"""Quality check: YOLO + ArcFace on live Sentinel frames.

Does not enroll, match, or raise alerts. Official street feeds stay off the FRS path.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

from sqlalchemy import select

from app.db import SessionLocal
from app.models.camera import Camera
from app.services.face import crop_quality_ok, detect_faces, person_crop, warmup_arcface
from app.workers.inference import detect_jpeg, inference_available
from app.workers.sentinel import PREVIEW_DIR, _grab_frame_sample, inference_urls


def _box_px(det: dict, w: int, h: int) -> tuple[int, int]:
    x1, y1, x2, y2 = det.get("x1"), det.get("y1"), det.get("x2"), det.get("y2")
    if None not in (x1, y1, x2, y2):
        return max(1, int(float(x2) - float(x1))), max(1, int(float(y2) - float(y1)))
    bbox = det.get("bbox") or {}
    return max(1, int(float(bbox.get("w") or 0) / 400 * w)), max(1, int(float(bbox.get("h") or 0) / 240 * h))


async def check_one(cam: Camera) -> dict:
    urls = inference_urls(cam.extra or {})
    jpeg = b""
    src = ""
    for url in urls:
        frame, _pts = await asyncio.to_thread(_grab_frame_sample, url)
        if frame:
            jpeg, src = frame, url.split("?")[0][-48:]
            break
    if not jpeg:
        return {"code": cam.code, "name": cam.name, "error": "no frame", "urls": len(urls)}

    PREVIEW_DIR.mkdir(parents=True, exist_ok=True)
    (PREVIEW_DIR / f"{cam.code}.jpg").write_bytes(jpeg)
    from PIL import Image
    from io import BytesIO

    im = Image.open(BytesIO(jpeg))
    w, h = im.size
    dets = await asyncio.to_thread(detect_jpeg, jpeg, camera_key=cam.code)
    people = [d for d in dets if d.get("object_type") == "person"]
    faces = await asyncio.to_thread(detect_faces, jpeg)

    crop_notes = []
    for person in people[:6]:
        crop = person_crop(jpeg, person)
        if crop is None:
            crop_notes.append({"ok": False, "reason": "no_crop"})
            continue
        ok, q = crop_quality_ok(crop)
        crop_notes.append({"ok": ok, **q, "min_side": min(crop.size)})

    return {
        "code": cam.code,
        "name": cam.name,
        "place": cam.address or cam.name,
        "src": src,
        "frame": f"{w}x{h}",
        "kb": round(len(jpeg) / 1024, 1),
        "yolo": {
            k: sum(1 for d in dets if d.get("object_type") == k) for k in ("person", "vehicle", "two-wheeler")
        },
        "person_boxes_px": [_box_px(d, w, h) for d in people[:8]],
        "face_count": len(faces),
        "faces": [
            {
                "score": round(float(f["det_score"]), 3),
                "w": int(f["bbox"][2] - f["bbox"][0]),
                "h": int(f["bbox"][3] - f["bbox"][1]),
            }
            for f in faces[:8]
        ],
        "person_crops": crop_notes,
    }


async def main() -> None:
    print("yolo", inference_available(), "arcface", warmup_arcface())
    async with SessionLocal() as db:
        cams = list(
            (await db.execute(select(Camera).where(Camera.source_type == "sentinel", Camera.is_active.is_(True)))).scalars()
        )
    prefer = ["SEN-1", "SEN-4", "SEN-14", "SEN-29", "SEN-2", "SEN-13", "SEN-5", "SEN-8"]
    by_code = {cam.code: cam for cam in cams}
    picked = [by_code[c] for c in prefer if c in by_code] or cams[:6]
    rows = []
    for cam in picked:
        row = await check_one(cam)
        rows.append(row)
        print(json.dumps(row, ensure_ascii=False))
    Path("/tmp/gusip-sentinel-face-check.json").write_text(json.dumps(rows, indent=2, ensure_ascii=False))
    faces = sum(int(r.get("face_count") or 0) for r in rows)
    people = sum(int((r.get("yolo") or {}).get("person") or 0) for r in rows)
    print(json.dumps({"cams": len(rows), "people": people, "faces": faces, "usable_face_48px": sum(
        1 for r in rows for f in r.get("faces") or [] if min(f.get("w") or 0, f.get("h") or 0) >= 48
    )}))


if __name__ == "__main__":
    asyncio.run(main())

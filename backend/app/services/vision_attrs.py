"""Cheap color/class from a YOLO box. Night PTZ cannot read plates; this still can."""

from __future__ import annotations

from io import BytesIO
from typing import Any

import numpy as np
from PIL import Image

YOLO_TO_CLASS = {
    "car": "car",
    "truck": "truck",
    "bus": "bus",
    "motorcycle": "two-wheeler",
    "bicycle": "two-wheeler",
}

CLASS_FAMILY: dict[str, frozenset[str]] = {
    "suv": frozenset({"suv", "car", "vehicle"}),
    "sedan": frozenset({"sedan", "car", "vehicle"}),
    "car": frozenset({"car", "suv", "sedan", "vehicle"}),
    "truck": frozenset({"truck", "vehicle"}),
    "bus": frozenset({"bus", "vehicle"}),
    "two-wheeler": frozenset({"two-wheeler", "motorcycle", "bicycle"}),
    "vehicle": frozenset({"vehicle", "car", "suv", "sedan", "truck", "bus"}),
}


def class_compatible(want: str, got: str) -> bool:
    w, g = (want or "").lower().strip(), (got or "").lower().strip()
    if not w or not g:
        return False
    family = CLASS_FAMILY.get(w, frozenset({w}))
    return g in family or w in CLASS_FAMILY.get(g, frozenset({g}))


def vehicle_class_of(det: dict[str, Any]) -> str:
    name = str(det.get("class_name") or det.get("vehicle_class") or "").lower()
    if name in YOLO_TO_CLASS:
        return YOLO_TO_CLASS[name]
    if det.get("object_type") == "two-wheeler":
        return "two-wheeler"
    if det.get("object_type") == "vehicle":
        return "car"
    return str(det.get("object_type") or "unknown")


def is_close_vehicle(det: dict[str, Any]) -> bool:
    if det.get("object_type") not in {"vehicle", "two-wheeler"}:
        return False
    h = float(det.get("frame_h") or 0) or 1.0
    w = max(1.0, float(det.get("x2", 0)) - float(det.get("x1", 0)))
    bh = max(1.0, float(det.get("y2", 0)) - float(det.get("y1", 0)))
    y2 = float(det.get("y2") or 0)
    return y2 > 0.40 * h and w >= 72 and bh >= 40


def estimate_color(jpeg: bytes | None, det: dict[str, Any]) -> str:
    """Dominant body color, ignoring headlight bloom and road."""
    if not jpeg:
        return "unknown"
    try:
        img = Image.open(BytesIO(jpeg)).convert("RGB")
    except Exception:
        return "unknown"
    x1 = max(0, int(det.get("x1") or 0))
    y1 = max(0, int(det.get("y1") or 0))
    x2 = min(img.width, int(det.get("x2") or 0))
    y2 = min(img.height, int(det.get("y2") or 0))
    if x2 - x1 < 12 or y2 - y1 < 12:
        return "unknown"
    # Upper 55% of the box is body; bumper/road is noisier at night.
    body = img.crop((x1, y1, x2, y1 + max(8, int(0.55 * (y2 - y1)))))
    arr = np.asarray(body)
    if arr.size < 50:
        return "unknown"
    r, g, b = arr[:, :, 0].astype(np.int16), arr[:, :, 1].astype(np.int16), arr[:, :, 2].astype(np.int16)
    mx = np.maximum(np.maximum(r, g), b)
    mn = np.minimum(np.minimum(r, g), b)
    luma = 0.299 * r + 0.587 * g + 0.114 * b
    sat = (mx - mn).astype(np.float32)
    # Drop blown headlights and near-black road.
    keep = (luma > 28) & (luma < 242)
    if int(keep.sum()) < 30:
        return "unknown"
    sl, ll = sat[keep], luma[keep]
    rr, gg, bb = r[keep], g[keep], b[keep]
    mean_l = float(ll.mean())
    mean_s = float(sl.mean())
    if mean_s < 22 and mean_l >= 145:
        return "white"
    if mean_s < 28 and mean_l <= 70:
        return "black"
    if mean_s < 24:
        return "gray"
    mean_r, mean_g, mean_b = float(rr.mean()), float(gg.mean()), float(bb.mean())
    if mean_r > mean_g + 25 and mean_r > mean_b + 18:
        return "red"
    if mean_g > mean_r + 12 and mean_g > mean_b + 8 and mean_r > 80:
        return "yellow"
    if mean_b > mean_r + 15 and mean_b > mean_g:
        return "blue"
    if mean_g > mean_r + 18 and mean_g > mean_b + 10:
        return "green"
    return "gray"


def enrich_detection(jpeg: bytes | None, det: dict[str, Any], *, plate_status: str = "unknown") -> dict[str, Any]:
    klass = vehicle_class_of(det)
    color = estimate_color(jpeg, det) if det.get("object_type") in {"vehicle", "two-wheeler"} else "unknown"
    close = is_close_vehicle(det)
    det["vehicle_class"] = klass
    det["color"] = color
    det["close"] = close
    det["plate_status"] = plate_status
    return det

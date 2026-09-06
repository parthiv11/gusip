"""Night extras that do not need glyphs: crowding, stopped, against-flow."""

from __future__ import annotations

from typing import Any


def analyze_scene(dets: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return zero or more scene events to ingest beside YOLO detections."""
    persons = [d for d in dets if d.get("object_type") == "person"]
    vehicles = [d for d in dets if d.get("object_type") in {"vehicle", "two-wheeler"}]
    out: list[dict[str, Any]] = []

    if len(persons) >= 5 or (len(persons) >= 3 and len(vehicles) >= 4) or len(dets) >= 12:
        out.append(
            {
                "event_type": "crowding",
                "object_type": "scene",
                "confidence": min(0.92, 0.55 + 0.04 * len(dets)),
                "attributes": {
                    "scene": "crowding",
                    "scene_score": 0.8,
                    "person_count": len(persons),
                    "vehicle_count": len(vehicles),
                },
                "bbox": {},
            }
        )

    for det in vehicles:
        hits = int(det.get("track_hits") or 0)
        iou = float(det.get("bbox_iou") or 0)
        if hits >= 3 and iou >= 0.72 and det.get("close"):
            out.append(
                {
                    "event_type": "stopped_vehicle",
                    "object_type": "vehicle",
                    "confidence": 0.74,
                    "local_track_id": det.get("local_track_id"),
                    "bbox": det.get("bbox") or {},
                    "attributes": {
                        "scene": "stopped_vehicle",
                        "scene_score": 0.74,
                        "color": det.get("color"),
                        "vehicle_class": det.get("vehicle_class"),
                        "class_name": det.get("class_name"),
                        "close": True,
                        "plate_status": det.get("plate_status") or "unreadable",
                        "track_hits": hits,
                    },
                }
            )
            break

    dxs = [float(d.get("dx") or 0) for d in vehicles if abs(float(d.get("dx") or 0)) >= 8]
    if len(dxs) >= 3:
        median = sorted(dxs)[len(dxs) // 2]
        for det in vehicles:
            dx = float(det.get("dx") or 0)
            if abs(dx) < 14 or not det.get("close"):
                continue
            if median == 0 or (dx > 0) == (median > 0):
                continue
            out.append(
                {
                    "event_type": "wrong_way",
                    "object_type": "vehicle",
                    "confidence": 0.7,
                    "local_track_id": det.get("local_track_id"),
                    "bbox": det.get("bbox") or {},
                    "attributes": {
                        "scene": "wrong_way",
                        "scene_score": 0.7,
                        "color": det.get("color"),
                        "vehicle_class": det.get("vehicle_class"),
                        "class_name": det.get("class_name"),
                        "close": True,
                        "plate_status": det.get("plate_status") or "unreadable",
                        "dx": dx,
                        "flow_dx": median,
                    },
                }
            )
            break
    return out

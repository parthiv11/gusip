from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.plates import format_plate, normalize_plate
from app.models.camera import Camera
from app.models.event import DetectionEvent, TrackPoint
from app.services.event_bus import bus
from app.services.matching import load_active_watchlist, maybe_raise_alert
from app.services.storage import generate_placeholder_snapshot, save_snapshot_png
from app.services.tracking import appearance_embedding, resolve_global_track


async def ingest_detection(db: AsyncSession, payload: dict[str, Any]) -> DetectionEvent | None:
    camera_id = payload["camera_id"]
    camera = await db.get(Camera, camera_id)
    if not camera:
        return None

    ts = payload.get("timestamp")
    if isinstance(ts, str):
        timestamp = datetime.fromisoformat(ts.replace("Z", "+00:00"))
    elif isinstance(ts, datetime):
        timestamp = ts if ts.tzinfo else ts.replace(tzinfo=timezone.utc)
    else:
        timestamp = datetime.now(timezone.utc)

    plate_raw = payload.get("plate_number")
    plate_norm = normalize_plate(plate_raw)
    attrs = payload.get("attributes") or {}
    embedding = payload.get("embedding") or appearance_embedding({**attrs, "object_type": payload.get("object_type")})
    global_track_id = await resolve_global_track(
        db,
        camera_id=camera.id,
        object_type=payload.get("object_type", "vehicle"),
        plate_normalized=plate_norm,
        embedding=embedding,
        timestamp=timestamp,
    )

    snap_url = payload.get("snapshot_url")
    if not snap_url:
        png = generate_placeholder_snapshot(
            payload.get("object_type", "object"),
            format_plate(plate_norm) or plate_raw,
            camera.code,
        )
        snap_url = save_snapshot_png(png, prefix=f"det-{camera.code}")

    event = DetectionEvent(
        camera_id=camera.id,
        timestamp=timestamp,
        event_type=payload.get("event_type", "detection"),
        object_type=payload.get("object_type", "vehicle"),
        local_track_id=payload.get("local_track_id"),
        global_track_id=global_track_id,
        plate_number=format_plate(plate_norm) or plate_raw,
        plate_normalized=plate_norm,
        confidence=float(payload.get("confidence", 0.9)),
        snapshot_url=snap_url,
        attributes=attrs,
        bbox=payload.get("bbox") or {},
        embedding=embedding,
    )
    db.add(event)
    await db.flush()

    db.add(
        TrackPoint(
            global_track_id=global_track_id,
            event_id=event.id,
            camera_id=camera.id,
            timestamp=timestamp,
            latitude=camera.latitude,
            longitude=camera.longitude,
            object_type=event.object_type,
            plate_normalized=plate_norm,
            confidence=event.confidence,
        )
    )

    camera.last_seen_at = timestamp
    if camera.status == "offline":
        camera.status = "online"

    watchlist = await load_active_watchlist(db)
    await maybe_raise_alert(db, event, camera, watchlist)
    await db.commit()
    await db.refresh(event)

    live = {
        "event_id": event.id,
        "camera_id": camera.id,
        "camera_code": camera.code,
        "city": camera.city,
        "lat": camera.latitude,
        "lon": camera.longitude,
        "timestamp": timestamp.isoformat(),
        "object_type": event.object_type,
        "plate": event.plate_number,
        "global_track_id": global_track_id,
        "confidence": event.confidence,
        "bbox": event.bbox,
        "attributes": attrs,
        "snapshot_url": snap_url,
    }
    await bus.publish_event(live)
    await bus.set_json(f"live:{camera.id}", live, ttl=20)
    return event

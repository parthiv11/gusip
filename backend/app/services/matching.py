from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from app.core.plates import normalize_plate
from app.models.camera import Camera
from app.models.event import Alert, DetectionEvent
from app.models.watchlist import WatchlistEntry
from app.services.event_bus import bus
from app.services.face import MATCH_THRESHOLD, cosine_score, is_face_embedding
from app.services.storage import generate_placeholder_snapshot, save_snapshot_png


def alert_fingerprint(watchlist_id: int, camera_id: int) -> str:
    """Dedup key: same watchlist entity on the same camera (FireHydrant/SecOps style)."""
    return f"{watchlist_id}:{camera_id}"


async def load_active_watchlist(db: AsyncSession) -> list[WatchlistEntry]:
    result = await db.execute(select(WatchlistEntry).where(WatchlistEntry.is_active.is_(True)))
    return list(result.scalars())


def match_entry(
    entry: WatchlistEntry,
    plate_norm: str | None,
    attrs: dict[str, Any],
    embedding: list[float] | None = None,
) -> tuple[bool, float]:
    if entry.entity_type == "vehicle" and plate_norm and entry.plate_normalized:
        if plate_norm == entry.plate_normalized:
            return True, 0.97
        # partial plate (common in poor lighting)
        if len(plate_norm) >= 6 and plate_norm[-4:] == entry.plate_normalized[-4:] and plate_norm[:2] == entry.plate_normalized[:2]:
            return True, 0.78
    if entry.entity_type == "person":
        if embedding and entry.face_embedding and is_face_embedding(embedding):
            score = cosine_score(embedding, entry.face_embedding)
            if score >= MATCH_THRESHOLD:
                return True, score
        notes = (entry.appearance_notes or "").lower()
        clothing = str(attrs.get("clothing", "")).lower()
        if notes and clothing and notes in clothing:
            return True, 0.72
        if attrs.get("watch_tag") == (entry.extra or {}).get("sim_tag"):
            return True, 0.88
    return False, 0.0


def _hit_count(payload: dict[str, Any] | None) -> int:
    try:
        return max(1, int((payload or {}).get("hit_count") or 1))
    except (TypeError, ValueError):
        return 1


async def collapse_duplicate_open_alerts(db: AsyncSession) -> int:
    """Merge leftover open rows (pre-unique-index) into one card per camera+watchlist."""
    rows = list(
        (await db.execute(select(Alert).where(Alert.status == "new").order_by(Alert.id.asc()))).scalars()
    )
    keep: dict[tuple[int, int], Alert] = {}
    closed = 0
    for alert in rows:
        key = (alert.watchlist_id, alert.camera_id)
        owner = keep.get(key)
        if owner is None:
            keep[key] = alert
            continue
        payload = dict(owner.payload or {})
        payload["hit_count"] = _hit_count(payload) + _hit_count(alert.payload)
        payload["last_seen"] = (alert.timestamp or datetime.now(timezone.utc)).isoformat()
        payload["coalesced"] = True
        owner.payload = payload
        flag_modified(owner, "payload")
        if alert.timestamp and (owner.timestamp is None or alert.timestamp > owner.timestamp):
            owner.timestamp = alert.timestamp
            owner.confidence = max(owner.confidence, alert.confidence)
            if alert.snapshot_url:
                owner.snapshot_url = alert.snapshot_url
        alert.status = "coalesced"
        closed += 1
    return closed


def _ws_payload(alert: Alert, entry: WatchlistEntry, camera: Camera, *, coalesced: bool) -> dict[str, Any]:
    extra = alert.payload or {}
    return {
        "id": alert.id,
        "camera_id": camera.id,
        "department_id": camera.department_id,
        "camera_code": camera.code,
        "camera_name": camera.name,
        "city": camera.city,
        "latitude": camera.latitude,
        "longitude": camera.longitude,
        "timestamp": alert.timestamp.isoformat() if alert.timestamp else None,
        "confidence": alert.confidence,
        "snapshot_url": alert.snapshot_url,
        "status": alert.status,
        "watchlist_id": entry.id,
        "category": entry.category,
        "entity_type": entry.entity_type,
        "name": entry.name,
        "plate": extra.get("plate"),
        "global_track_id": extra.get("global_track_id"),
        "priority": entry.priority,
        "description": entry.description,
        "source_type": camera.source_type,
        "hit_count": _hit_count(extra),
        "coalesced": coalesced,
        "fingerprint": alert_fingerprint(entry.id, camera.id),
    }


async def _bump_open_alert(
    db: AsyncSession,
    open_row: Alert,
    event: DetectionEvent,
    camera: Camera,
    entry: WatchlistEntry,
    confidence: float,
) -> Alert:
    extra = dict(open_row.payload or {})
    extra["hit_count"] = _hit_count(extra) + 1
    extra["last_seen"] = (event.timestamp or datetime.now(timezone.utc)).isoformat()
    extra["global_track_id"] = event.global_track_id
    extra["plate"] = event.plate_number
    extra["coalesced"] = True
    extra["source_type"] = camera.source_type
    extra["fingerprint"] = alert_fingerprint(entry.id, camera.id)
    extra["match_score"] = confidence
    extra["match_kind"] = "face" if entry.entity_type == "person" else "plate"
    open_row.payload = extra
    flag_modified(open_row, "payload")
    open_row.confidence = max(open_row.confidence, confidence)
    if event.timestamp:
        open_row.timestamp = event.timestamp
    open_row.event_id = event.id
    if event.snapshot_url:
        open_row.snapshot_url = event.snapshot_url
    await db.flush()
    await bus.publish_alert(_ws_payload(open_row, entry, camera, coalesced=True))
    return open_row


async def maybe_raise_alert(
    db: AsyncSession,
    event: DetectionEvent,
    camera: Camera,
    watchlist: list[WatchlistEntry],
) -> Alert | None:
    plate_norm = event.plate_normalized or normalize_plate(event.plate_number)
    best: tuple[WatchlistEntry, float] | None = None
    for entry in watchlist:
        ok, conf = match_entry(entry, plate_norm, event.attributes or {}, event.embedding)
        if ok and (best is None or conf > best[1]):
            best = (entry, conf)
    if not best:
        return None

    entry, confidence = best
    open_row = (
        await db.execute(
            select(Alert)
            .where(
                Alert.watchlist_id == entry.id,
                Alert.camera_id == camera.id,
                Alert.status == "new",
            )
            .order_by(Alert.id.asc())
            .limit(1)
            .with_for_update()
        )
    ).scalar_one_or_none()
    if open_row:
        return await _bump_open_alert(db, open_row, event, camera, entry, confidence)

    snap_url = event.snapshot_url
    if not snap_url:
        snap = generate_placeholder_snapshot(entry.category.replace("_", " ").title(), event.plate_number, camera.code)
        snap_url = save_snapshot_png(snap, prefix=f"alert-{camera.code}")
    now = event.timestamp or datetime.now(timezone.utc)
    alert = Alert(
        event_id=event.id,
        watchlist_id=entry.id,
        camera_id=camera.id,
        timestamp=now,
        confidence=confidence,
        snapshot_url=snap_url,
        clip_url=None,
        status="new",
        payload={
            "camera_code": camera.code,
            "camera_name": camera.name,
            "city": camera.city,
            "lat": camera.latitude,
            "lon": camera.longitude,
            "entity_type": entry.entity_type,
            "category": entry.category,
            "matched_name": entry.name,
            "plate": event.plate_number,
            "global_track_id": event.global_track_id,
            "priority": entry.priority,
            "source_type": camera.source_type,
            "hit_count": 1,
            "fingerprint": alert_fingerprint(entry.id, camera.id),
            "match_score": confidence,
            "match_kind": "face" if entry.entity_type == "person" else "plate",
        },
    )
    try:
        async with db.begin_nested():
            db.add(alert)
            await db.flush()
            await db.refresh(alert)
    except IntegrityError:
        open_row = (
            await db.execute(
                select(Alert)
                .where(
                    Alert.watchlist_id == entry.id,
                    Alert.camera_id == camera.id,
                    Alert.status == "new",
                )
                .order_by(Alert.id.asc())
                .limit(1)
            )
        ).scalar_one_or_none()
        if open_row:
            return await _bump_open_alert(db, open_row, event, camera, entry, confidence)
        raise

    await bus.publish_alert(_ws_payload(alert, entry, camera, coalesced=False))
    return alert

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import numpy as np
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.event import DetectionEvent


def cosine(a: list[float], b: list[float]) -> float:
    va = np.array(a, dtype=float)
    vb = np.array(b, dtype=float)
    na, nb = np.linalg.norm(va), np.linalg.norm(vb)
    if na == 0 or nb == 0:
        return 0.0
    return float(np.dot(va, vb) / (na * nb))


def appearance_embedding(attrs: dict) -> list[float]:
    """Deterministic appearance vector for PoC Re-ID (swap for OSNet in production)."""
    color = str(attrs.get("color", "unknown")).lower()
    klass = str(attrs.get("vehicle_class", attrs.get("object_type", "unknown"))).lower()
    make = str(attrs.get("make", "")).lower()
    rng = np.random.default_rng(abs(hash(color + klass + make)) % (2**32))
    vec = rng.normal(0, 1, 64)
    color_idx = abs(hash(color)) % 64
    class_idx = abs(hash(klass)) % 64
    vec[color_idx] += 3.0
    vec[class_idx] += 2.0
    n = np.linalg.norm(vec)
    return (vec / n).tolist()


async def resolve_global_track(
    db: AsyncSession,
    *,
    camera_id: int,
    object_type: str,
    plate_normalized: str | None,
    embedding: list[float] | None,
    timestamp: datetime,
) -> str:
    """Multi-camera Re-ID: plate-first, then embedding similarity within a time window."""
    window_start = timestamp - timedelta(minutes=45)

    if plate_normalized:
        q = await db.execute(
            select(DetectionEvent)
            .where(
                DetectionEvent.plate_normalized == plate_normalized,
                DetectionEvent.timestamp >= window_start,
            )
            .order_by(DetectionEvent.timestamp.desc())
            .limit(1)
        )
        prev = q.scalar_one_or_none()
        if prev and prev.global_track_id:
            return prev.global_track_id
        return f"veh-{plate_normalized}"

    if embedding:
        q = await db.execute(
            select(DetectionEvent)
            .where(
                DetectionEvent.object_type == object_type,
                DetectionEvent.timestamp >= window_start,
                DetectionEvent.embedding.is_not(None),
            )
            .order_by(DetectionEvent.timestamp.desc())
            .limit(40)
        )
        best_id, best_score = None, 0.82
        for ev in q.scalars():
            if not ev.embedding:
                continue
            score = cosine(embedding, ev.embedding)
            if score > best_score and ev.global_track_id:
                best_score = score
                best_id = ev.global_track_id
        if best_id:
            return best_id

    stamp = timestamp.astimezone(timezone.utc).strftime("%H%M%S")
    return f"{object_type[:3]}-{camera_id}-{stamp}"

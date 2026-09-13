"""Purge aged, non-evidentiary detection data.

docs/deployment.md documents a 90-day object-store lifecycle for snapshots and
docs/security.md's hardening checklist still lists "DPDP / police data SOPs:
retention" as undecided — so this only purges the high-volume, non-evidentiary
tail (raw DetectionEvent rows and TrackPoint breadcrumbs) and always leaves
alone anything an Alert still references. Alerts, watchlist entries, and audit
logs are never touched here: how long an actual incident record is kept is a
legal/departmental decision, not one this sweep makes on its own.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, select

from app.config import get_settings
from app.db import SessionLocal
from app.models.event import Alert, DetectionEvent, TrackPoint
from app.services.storage import DATA_DIR

log = logging.getLogger("gusip.retention")
settings = get_settings()

_BATCH_SIZE = 500


def _delete_snapshot_file(snapshot_url: str | None) -> bool:
    if not snapshot_url:
        return False
    name = snapshot_url.rsplit("/", 1)[-1]
    if not name or "/" in name or ".." in name:
        return False
    path = DATA_DIR / "snapshots" / name
    try:
        path.unlink()
        return True
    except FileNotFoundError:
        return False
    except OSError:
        log.warning("Could not remove aged snapshot file %s", name)
        return False


async def purge_expired(now: datetime | None = None) -> dict[str, int]:
    """Delete expired DetectionEvent/TrackPoint rows and their snapshot files.

    Returns counts for logging/testing. Safe to call repeatedly — each call
    only ever looks at rows already past the cutoff.
    """
    days = settings.detection_retention_days
    if days <= 0:
        return {"events_deleted": 0, "trackpoints_deleted": 0, "files_deleted": 0}
    cutoff = (now or datetime.now(timezone.utc)) - timedelta(days=days)

    events_deleted = 0
    files_deleted = 0
    async with SessionLocal() as db:
        referenced = select(Alert.event_id).where(Alert.event_id.is_not(None))
        while True:
            rows = (
                (
                    await db.execute(
                        select(DetectionEvent.id, DetectionEvent.snapshot_url)
                        .where(DetectionEvent.timestamp < cutoff)
                        .where(DetectionEvent.id.not_in(referenced))
                        .limit(_BATCH_SIZE)
                    )
                )
                .all()
            )
            if not rows:
                break
            ids = [r.id for r in rows]
            for row in rows:
                if _delete_snapshot_file(row.snapshot_url):
                    files_deleted += 1
            await db.execute(delete(DetectionEvent).where(DetectionEvent.id.in_(ids)))
            await db.commit()
            events_deleted += len(ids)
            if len(rows) < _BATCH_SIZE:
                break

        trackpoints_deleted = 0
        while True:
            result = await db.execute(
                delete(TrackPoint)
                .where(TrackPoint.timestamp < cutoff)
                .where(TrackPoint.id.in_(select(TrackPoint.id).where(TrackPoint.timestamp < cutoff).limit(_BATCH_SIZE)))
            )
            await db.commit()
            n = result.rowcount or 0
            trackpoints_deleted += n
            if n < _BATCH_SIZE:
                break

    if events_deleted or trackpoints_deleted:
        log.info(
            "retention sweep: purged %s detection events, %s track points, %s snapshot files (cutoff=%s)",
            events_deleted,
            trackpoints_deleted,
            files_deleted,
            cutoff.isoformat(),
        )
    return {
        "events_deleted": events_deleted,
        "trackpoints_deleted": trackpoints_deleted,
        "files_deleted": files_deleted,
    }

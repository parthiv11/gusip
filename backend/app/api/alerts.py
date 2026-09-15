from datetime import datetime, timedelta, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.audit import write_audit
from app.core.break_glass import department_scope
from app.core.policy import assert_department_allowed, require_capability
from app.core.security import client_ip, get_current_user
from app.db import get_db
from app.models.camera import Camera
from app.models.event import Alert, DetectionEvent
from app.models.user import User
from app.schemas.common import AlertOut

router = APIRouter(prefix="/alerts", tags=["alerts"])

ANOMALY_TYPES = ("crowding", "stopped_vehicle", "wrong_way")

_ALERT_LOAD = (
    selectinload(Alert.camera).selectinload(Camera.department),
    selectinload(Alert.watchlist),
)


@router.get("", response_model=list[AlertOut])
async def list_alerts(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
    status: str | None = None,
    limit: int = 100,
):
    q = select(Alert).options(*_ALERT_LOAD)
    scoped_to = await department_scope(user)
    if scoped_to is not None:
        q = q.join(Camera, Camera.id == Alert.camera_id).where(Camera.department_id == scoped_to)
    if status:
        q = q.where(Alert.status == status)
    else:
        q = q.where(Alert.status != "coalesced")
    q = q.order_by(Alert.timestamp.desc()).limit(limit)
    rows = list((await db.execute(q)).scalars())
    await write_audit(
        db,
        user_id=user.id,
        username=user.username,
        action="list_alerts",
        resource="alerts",
        details={"status": status, "count": len(rows)},
        ip_address=client_ip(request),
    )
    await db.commit()
    return rows


@router.get("/anomalies")
async def list_anomalies(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
    hours: int = 24,
    limit: int = 200,
):
    """Scene anomalies (crowding, stopped vehicle, wrong-way) from analyze_scene()
    (backend/app/services/scene.py). These ride on DetectionEvent, not Alert,
    since they have no watchlist match — Alert.watchlist_id is required, so
    there's no schema path for a non-watchlist event to become an Alert row.
    Surfaced here as their own list rather than force-fitting them into the
    watchlist alert inbox."""
    since = datetime.now(timezone.utc) - timedelta(hours=hours)
    scoped_to = await department_scope(user)
    q = (
        select(DetectionEvent)
        .join(Camera, Camera.id == DetectionEvent.camera_id)
        .options(selectinload(DetectionEvent.camera))
        .where(DetectionEvent.event_type.in_(ANOMALY_TYPES), DetectionEvent.timestamp >= since)
        .order_by(DetectionEvent.timestamp.desc())
        .limit(limit)
    )
    if scoped_to is not None:
        q = q.where(Camera.department_id == scoped_to)
    rows = list((await db.execute(q)).scalars())
    payload = [
        {
            "id": e.id,
            "timestamp": e.timestamp.isoformat() if e.timestamp else None,
            "event_type": e.event_type,
            "camera_id": e.camera_id,
            "camera_code": e.camera.code if e.camera else None,
            "camera_name": e.camera.name if e.camera else None,
            "city": e.camera.city if e.camera else None,
            "confidence": e.confidence,
            "snapshot_url": e.snapshot_url,
            "attributes": e.attributes or {},
        }
        for e in rows
    ]
    await write_audit(
        db,
        user_id=user.id,
        username=user.username,
        action="list_anomalies",
        resource="alerts/anomalies",
        details={"hours": hours, "count": len(payload)},
        ip_address=client_ip(request),
    )
    await db.commit()
    return {"count": len(payload), "hours": hours, "rows": payload}


@router.post("/{alert_id}/ack", response_model=AlertOut)
async def ack_alert(
    alert_id: int,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_capability("ack_alert"))],
    notes: str | None = None,
):
    result = await db.execute(
        select(Alert).options(*_ALERT_LOAD).where(Alert.id == alert_id)
    )
    alert = result.scalar_one_or_none()
    if not alert:
        raise HTTPException(404, "Alert not found")
    scoped_to = await department_scope(user)
    cam_dept = alert.camera.department_id if alert.camera else None
    assert_department_allowed(user, cam_dept, scoped_to)
    alert.status = "acknowledged"
    alert.acknowledged_by = user.username
    alert.acknowledged_at = datetime.now(timezone.utc)
    if notes:
        alert.notes = notes
    siblings = list(
        (
            await db.execute(
                select(Alert).where(
                    Alert.watchlist_id == alert.watchlist_id,
                    Alert.camera_id == alert.camera_id,
                    Alert.status == "new",
                    Alert.id != alert.id,
                )
            )
        ).scalars()
    )
    for sib in siblings:
        sib.status = "acknowledged"
        sib.acknowledged_by = user.username
        sib.acknowledged_at = alert.acknowledged_at
        sib.notes = notes or "acked with group"
    await write_audit(
        db,
        user_id=user.id,
        username=user.username,
        action="ack_alert",
        resource=f"alerts/{alert_id}",
        ip_address=client_ip(request),
    )
    await db.commit()
    await db.refresh(alert)
    return alert

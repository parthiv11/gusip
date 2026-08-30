from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.break_glass import department_scope
from app.core.policy import require_capability
from app.core.security import require_roles
from app.db import get_db
from app.models.audit import AuditLog
from app.models.camera import Camera
from app.models.event import Alert, DetectionEvent
from app.models.user import User

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/audit")
async def audit_logs(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_roles("system_admin", "department_coordinator"))],
    limit: int = 200,
    username: str | None = None,
    action: str | None = None,
):
    q = select(AuditLog).order_by(AuditLog.created_at.desc()).limit(limit)
    scoped_to = await department_scope(user)
    if scoped_to is not None:
        q = q.where(AuditLog.department_id == scoped_to)
    if username:
        q = q.where(AuditLog.username == username)
    if action:
        q = q.where(AuditLog.action == action)
    rows = list((await db.execute(q)).scalars())
    return [
        {
            "id": r.id,
            "username": r.username,
            "action": r.action,
            "resource": r.resource,
            "details": r.details,
            "ip_address": r.ip_address,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in rows
    ]


@router.get("/stats")
async def stats(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_capability("admin_stats"))],
):
    scoped_to = await department_scope(user)
    camera_filter = (Camera.department_id == scoped_to,) if scoped_to is not None else ()
    cameras = (await db.execute(select(func.count(Camera.id)).where(*camera_filter))).scalar() or 0
    online = (
        await db.execute(select(func.count(Camera.id)).where(Camera.status == "online", *camera_filter))
    ).scalar() or 0
    event_q = select(func.count(DetectionEvent.id)).join(Camera, Camera.id == DetectionEvent.camera_id)
    alert_q = select(func.count(Alert.id)).join(Camera, Camera.id == Alert.camera_id)
    if scoped_to is not None:
        event_q = event_q.where(Camera.department_id == scoped_to)
        alert_q = alert_q.where(Camera.department_id == scoped_to)
    events = (await db.execute(event_q)).scalar() or 0
    alerts = (await db.execute(alert_q)).scalar() or 0
    open_q = select(func.count(Alert.id)).join(Camera, Camera.id == Alert.camera_id).where(Alert.status == "new")
    if scoped_to is not None:
        open_q = open_q.where(Camera.department_id == scoped_to)
    open_alerts = (
        await db.execute(open_q)
    ).scalar() or 0
    by_source = (
        await db.execute(
            select(Camera.source_type, func.count(Camera.id)).where(*camera_filter).group_by(Camera.source_type)
        )
    ).all()
    by_dept = (
        await db.execute(select(Camera.city, func.count(Camera.id)).where(*camera_filter).group_by(Camera.city))
    ).all()
    return {
        "cameras": cameras,
        "online": online,
        "offline": cameras - online,
        "events": events,
        "alerts": alerts,
        "open_alerts": open_alerts,
        "by_source": {k: v for k, v in by_source},
        "by_city": {k: v for k, v in by_dept},
    }

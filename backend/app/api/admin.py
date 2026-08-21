from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_current_user, require_roles
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
    _user: Annotated[User, Depends(get_current_user)],
):
    cameras = (await db.execute(select(func.count(Camera.id)))).scalar() or 0
    online = (
        await db.execute(select(func.count(Camera.id)).where(Camera.status == "online"))
    ).scalar() or 0
    events = (await db.execute(select(func.count(DetectionEvent.id)))).scalar() or 0
    alerts = (await db.execute(select(func.count(Alert.id)))).scalar() or 0
    open_alerts = (
        await db.execute(select(func.count(Alert.id)).where(Alert.status == "new"))
    ).scalar() or 0
    by_source = (
        await db.execute(select(Camera.source_type, func.count(Camera.id)).group_by(Camera.source_type))
    ).all()
    by_dept = (
        await db.execute(select(Camera.city, func.count(Camera.id)).group_by(Camera.city))
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

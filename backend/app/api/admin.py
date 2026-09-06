from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.audit import write_audit
from app.core.break_glass import department_scope
from app.core.policy import (
    BUILTIN_SLUGS,
    CAPABILITY_CATALOG,
    SUPER_ADMIN_ONLY,
    capabilities_for,
    known_role_slugs,
    normalize_role_slug,
    require_capability,
    role_display_name,
    sanitize_caps,
)
from app.core.security import client_ip, hash_password, require_roles
from app.db import get_db
from app.models.audit import AuditLog
from app.models.camera import Camera, Department
from app.models.event import Alert, DetectionEvent
from app.models.role import Role
from app.models.user import User
from app.services.iam import refresh_role_cache

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


class RoleIn(BaseModel):
    slug: str | None = None
    name: str = Field(min_length=2, max_length=128)
    description: str = ""
    capabilities: list[str] = Field(default_factory=list)
    statewide: bool = False


class UserAssign(BaseModel):
    role: str | None = None
    department_id: int | None = None
    is_active: bool | None = None
    full_name: str | None = None
    email: str | None = None


class UserCreateAdmin(BaseModel):
    username: str = Field(min_length=3, max_length=64)
    password: str = Field(min_length=10, max_length=128)
    full_name: str = Field(min_length=2, max_length=128)
    email: str = Field(min_length=5, max_length=128)
    role: str
    department_id: int | None = None


def _role_out(row: Role, counts: dict[str, int]) -> dict[str, Any]:
    caps = capabilities_for(row.slug) if row.builtin else sanitize_caps(row.capabilities or [])
    if row.statewide and "statewide" not in caps:
        caps = sorted({*caps, "statewide"})
    return {
        "slug": row.slug,
        "name": row.name,
        "description": row.description or "",
        "capabilities": caps,
        "statewide": row.statewide or "statewide" in caps,
        "builtin": row.builtin,
        "privileged": bool(SUPER_ADMIN_ONLY & set(caps)),
        "user_count": counts.get(row.slug, 0),
    }


async def _role_counts(db: AsyncSession) -> dict[str, int]:
    rows = (await db.execute(select(User.role, func.count(User.id)).group_by(User.role))).all()
    return {str(slug): int(n) for slug, n in rows}


async def _active_super_admins(db: AsyncSession) -> int:
    return int(
        (
            await db.execute(
                select(func.count(User.id)).where(User.role == "system_admin", User.is_active.is_(True))
            )
        ).scalar()
        or 0
    )


async def _assert_role_exists(db: AsyncSession, slug: str) -> None:
    await refresh_role_cache(db)
    if slug in known_role_slugs():
        return
    raise HTTPException(400, f"Unknown role '{slug}'")


@router.get("/iam/catalog")
async def iam_catalog(
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_capability("manage_roles"))],
):
    await refresh_role_cache(db)
    return {
        "capabilities": [{"id": cid, "label": label, "privileged": cid in SUPER_ADMIN_ONLY} for cid, label in CAPABILITY_CATALOG],
        "privileged": sorted(SUPER_ADMIN_ONLY),
    }


@router.get("/iam/roles")
async def list_roles(
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_capability("manage_roles"))],
):
    await refresh_role_cache(db)
    counts = await _role_counts(db)
    rows = list((await db.execute(select(Role).order_by(Role.builtin.desc(), Role.name))).scalars())
    return [_role_out(row, counts) for row in rows]


@router.post("/iam/roles", status_code=201)
async def create_role(
    payload: RoleIn,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    admin: Annotated[User, Depends(require_capability("manage_roles"))],
):
    slug = normalize_role_slug(payload.slug or payload.name)
    if slug in BUILTIN_SLUGS or await db.scalar(select(Role).where(Role.slug == slug)):
        raise HTTPException(409, "That role id already exists")
    caps = sanitize_caps(payload.capabilities)
    if payload.statewide:
        caps = sorted({*caps, "statewide"})
    row = Role(
        slug=slug,
        name=payload.name.strip(),
        description=(payload.description or "").strip(),
        capabilities=caps,
        statewide="statewide" in caps,
        builtin=False,
    )
    db.add(row)
    await write_audit(
        db,
        user_id=admin.id,
        username=admin.username,
        action="create_role",
        resource=f"roles/{slug}",
        details={"capabilities": caps, "statewide": row.statewide},
        ip_address=client_ip(request),
        department_id=admin.department_id,
    )
    await db.commit()
    await db.refresh(row)
    await refresh_role_cache(db)
    counts = await _role_counts(db)
    return _role_out(row, counts)


@router.patch("/iam/roles/{slug}")
async def update_role(
    slug: str,
    payload: RoleIn,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    admin: Annotated[User, Depends(require_capability("manage_roles"))],
):
    row = await db.scalar(select(Role).where(Role.slug == slug))
    if row is None:
        raise HTTPException(404, "Role not found")
    if row.builtin:
        raise HTTPException(400, "Built-in roles cannot be edited — clone them as a custom role")
    caps = sanitize_caps(payload.capabilities)
    if payload.statewide:
        caps = sorted({*caps, "statewide"})
    row.name = payload.name.strip()
    row.description = (payload.description or "").strip()
    row.capabilities = caps
    row.statewide = "statewide" in caps
    await write_audit(
        db,
        user_id=admin.id,
        username=admin.username,
        action="update_role",
        resource=f"roles/{slug}",
        details={"capabilities": caps, "statewide": row.statewide},
        ip_address=client_ip(request),
        department_id=admin.department_id,
    )
    await db.commit()
    await refresh_role_cache(db)
    counts = await _role_counts(db)
    return _role_out(row, counts)


@router.delete("/iam/roles/{slug}")
async def delete_role(
    slug: str,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    admin: Annotated[User, Depends(require_capability("manage_roles"))],
):
    row = await db.scalar(select(Role).where(Role.slug == slug))
    if row is None:
        raise HTTPException(404, "Role not found")
    if row.builtin:
        raise HTTPException(400, "Built-in roles cannot be removed")
    n = int((await db.execute(select(func.count(User.id)).where(User.role == slug))).scalar() or 0)
    if n:
        raise HTTPException(409, f"{n} user(s) still assigned — reassign them before removing this role")
    await db.delete(row)
    await write_audit(
        db,
        user_id=admin.id,
        username=admin.username,
        action="delete_role",
        resource=f"roles/{slug}",
        ip_address=client_ip(request),
        department_id=admin.department_id,
    )
    await db.commit()
    await refresh_role_cache(db)
    return {"ok": True, "slug": slug}


@router.get("/iam/users")
async def list_users(
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_capability("manage_roles"))],
):
    await refresh_role_cache(db)
    rows = list(
        (
            await db.execute(select(User).options(selectinload(User.department)).order_by(User.username))
        ).scalars()
    )
    return [
        {
            "id": u.id,
            "username": u.username,
            "full_name": u.full_name,
            "email": u.email,
            "role": u.role,
            "role_name": role_display_name(u.role),
            "department_id": u.department_id,
            "department_name": u.department.name if u.department else None,
            "is_active": u.is_active,
            "capabilities": capabilities_for(u.role),
            "scope": "statewide" if "statewide" in capabilities_for(u.role) else "department",
        }
        for u in rows
    ]


@router.post("/iam/users", status_code=201)
async def create_user_admin(
    payload: UserCreateAdmin,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    admin: Annotated[User, Depends(require_capability("manage_roles"))],
):
    role = normalize_role_slug(payload.role)
    await _assert_role_exists(db, role)
    if await db.scalar(select(User).where(User.username == payload.username.strip().lower())):
        raise HTTPException(409, "Username already exists")
    if await db.scalar(select(User).where(User.email == payload.email.strip().lower())):
        raise HTTPException(409, "Email already exists")
    if payload.department_id is not None:
        dept = await db.scalar(select(Department).where(Department.id == payload.department_id))
        if dept is None:
            raise HTTPException(400, "Unknown department")
    user = User(
        username=payload.username.strip().lower(),
        full_name=payload.full_name.strip(),
        email=payload.email.strip().lower(),
        hashed_password=hash_password(payload.password),
        role=role,
        department_id=payload.department_id,
        is_active=True,
    )
    db.add(user)
    await write_audit(
        db,
        user_id=admin.id,
        username=admin.username,
        action="create_user",
        resource=f"users/{user.username}",
        details={"role": role, "department_id": payload.department_id},
        ip_address=client_ip(request),
        department_id=admin.department_id,
    )
    await db.commit()
    await db.refresh(user)
    return {"id": user.id, "username": user.username, "role": user.role}


@router.patch("/iam/users/{user_id}")
async def assign_user(
    user_id: int,
    payload: UserAssign,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    admin: Annotated[User, Depends(require_capability("manage_roles"))],
):
    await refresh_role_cache(db)
    user = await db.scalar(select(User).where(User.id == user_id))
    if user is None:
        raise HTTPException(404, "User not found")
    before = {"role": user.role, "department_id": user.department_id, "is_active": user.is_active}
    if payload.role is not None:
        role = normalize_role_slug(payload.role)
        await _assert_role_exists(db, role)
        if user.role == "system_admin" and role != "system_admin" and await _active_super_admins(db) <= 1:
            raise HTTPException(400, "Cannot demote the last super administrator")
        user.role = role
    if "department_id" in payload.model_fields_set:
        if payload.department_id is not None:
            dept = await db.scalar(select(Department).where(Department.id == payload.department_id))
            if dept is None:
                raise HTTPException(400, "Unknown department")
        user.department_id = payload.department_id
    if payload.is_active is not None:
        if user.role == "system_admin" and payload.is_active is False and await _active_super_admins(db) <= 1:
            raise HTTPException(400, "Cannot deactivate the last super administrator")
        user.is_active = payload.is_active
    if payload.full_name is not None:
        user.full_name = payload.full_name.strip()
    if payload.email is not None:
        user.email = payload.email.strip().lower()
    await write_audit(
        db,
        user_id=admin.id,
        username=admin.username,
        action="assign_role",
        resource=f"users/{user.username}",
        details={"before": before, "after": {"role": user.role, "department_id": user.department_id, "is_active": user.is_active}},
        ip_address=client_ip(request),
        department_id=admin.department_id,
    )
    await db.commit()
    return {
        "id": user.id,
        "username": user.username,
        "role": user.role,
        "department_id": user.department_id,
        "is_active": user.is_active,
    }

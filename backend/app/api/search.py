from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.audit import write_audit
from app.core.break_glass import department_scope, get_grant
from app.core.plates import normalize_plate
from app.core.policy import require_capability, validate_purpose
from app.core.security import client_ip
from app.db import get_db
from app.models.camera import Camera
from app.models.event import DetectionEvent, TrackPoint
from app.models.user import User
from app.schemas.common import EventOut, SearchQuery, TrackPointOut

router = APIRouter(prefix="/search", tags=["search"])


async def _audit_search(
    db: AsyncSession,
    user: User,
    request: Request,
    action: str,
    resource: str,
    details: dict,
) -> None:
    grant = await get_grant(user.id)
    payload = dict(details)
    payload["break_glass"] = bool(grant)
    if grant:
        payload["break_glass_reason"] = grant.get("reason")
    await write_audit(
        db,
        user_id=user.id,
        username=user.username,
        action=action,
        resource=resource,
        details=payload,
        ip_address=client_ip(request),
        department_id=user.department_id,
    )


def _apply_dept_scope(q, scoped_to: int | None):
    if scoped_to is None:
        return q
    return q.join(Camera, Camera.id == DetectionEvent.camera_id).where(Camera.department_id == scoped_to)


@router.post("/events", response_model=list[EventOut])
async def search_events(
    body: SearchQuery,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_capability("search"))],
):
    purpose = validate_purpose(body.purpose)
    scoped_to = await department_scope(user)
    q = select(DetectionEvent)
    q = _apply_dept_scope(q, scoped_to)
    if body.plate:
        norm = normalize_plate(body.plate)
        q = q.where(
            (DetectionEvent.plate_normalized == norm) | (DetectionEvent.plate_number.ilike(f"%{body.plate}%"))
        )
    if body.object_type:
        q = q.where(DetectionEvent.object_type == body.object_type)
    if body.camera_id:
        q = q.where(DetectionEvent.camera_id == body.camera_id)
    if body.event_type:
        q = q.where(DetectionEvent.event_type == body.event_type)
    if body.from_ts:
        q = q.where(DetectionEvent.timestamp >= body.from_ts)
    if body.to_ts:
        q = q.where(DetectionEvent.timestamp <= body.to_ts)
    if body.color:
        q = q.where(DetectionEvent.attributes["color"].astext == body.color)
    if body.vehicle_class:
        q = q.where(DetectionEvent.attributes["vehicle_class"].astext == body.vehicle_class)
    if body.city:
        if scoped_to is None:
            q = q.join(Camera, Camera.id == DetectionEvent.camera_id)
        q = q.where(Camera.city == body.city)

    rows = list((await db.execute(q.order_by(DetectionEvent.timestamp.desc()).limit(body.limit))).scalars())
    dumped = body.model_dump(mode="json")
    dumped["purpose"] = purpose
    await _audit_search(db, user, request, "search_events", "search/events", dumped)
    await db.commit()
    return rows


@router.get("/tracks/{global_track_id}", response_model=list[TrackPointOut])
async def track_history(
    global_track_id: str,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_capability("search"))],
    purpose: Annotated[str, Query()],
):
    purpose = validate_purpose(purpose)
    scoped_to = await department_scope(user)
    q = (
        select(TrackPoint)
        .options(selectinload(TrackPoint.camera))
        .where(TrackPoint.global_track_id == global_track_id)
        .order_by(TrackPoint.timestamp.asc())
    )
    points = list((await db.execute(q)).scalars())
    if scoped_to is not None:
        points = [p for p in points if p.camera and p.camera.department_id == scoped_to]
    out = []
    for p in points:
        item = TrackPointOut.model_validate(p)
        if p.camera:
            item.camera_code = p.camera.code
            item.camera_name = p.camera.name
            item.city = p.camera.city
        out.append(item)
    await _audit_search(
        db,
        user,
        request,
        "view_track",
        f"tracks/{global_track_id}",
        {"purpose": purpose},
    )
    await db.commit()
    return out


@router.get("/plate/{plate}", response_model=list[TrackPointOut])
async def plate_route(
    plate: str,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_capability("search"))],
    purpose: Annotated[str, Query()],
):
    purpose = validate_purpose(purpose)
    scoped_to = await department_scope(user)
    norm = normalize_plate(plate)
    q = (
        select(TrackPoint)
        .options(selectinload(TrackPoint.camera))
        .where(TrackPoint.plate_normalized == norm)
        .order_by(TrackPoint.timestamp.asc())
    )
    points = list((await db.execute(q)).scalars())
    if scoped_to is not None:
        points = [p for p in points if p.camera and p.camera.department_id == scoped_to]
    out = []
    for p in points:
        item = TrackPointOut.model_validate(p)
        if p.camera:
            item.camera_code = p.camera.code
            item.camera_name = p.camera.name
            item.city = p.camera.city
        out.append(item)
    await _audit_search(
        db,
        user,
        request,
        "search_plate_route",
        f"plates/{norm}",
        {"purpose": purpose, "plate": norm},
    )
    await db.commit()
    return out

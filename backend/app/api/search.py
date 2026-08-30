from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, UploadFile
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
from app.models.watchlist import WatchlistEntry
from app.schemas.common import EventOut, FaceSearchOut, FaceWatchlistHit, SearchQuery, TrackPointOut
from app.services.face import MATCH_THRESHOLD, FaceEngineError, cosine_score, embed_image_bytes, is_face_embedding

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


def _decorate_track_points(points) -> list[TrackPointOut]:
    raw: list[TrackPointOut] = []
    for p in points:
        item = TrackPointOut.model_validate(p)
        if p.camera:
            item.camera_code = p.camera.code
            item.camera_name = p.camera.name
            item.city = p.camera.city
        raw.append(item)
    if not raw:
        return []
    dwells: list[TrackPointOut] = []
    for item in raw:
        if dwells and dwells[-1].camera_id == item.camera_id:
            prev = dwells[-1]
            dwells[-1] = item.model_copy(
                update={
                    "hits": prev.hits + 1,
                    "first_seen": prev.first_seen or prev.timestamp,
                }
            )
        else:
            dwells.append(item.model_copy(update={"hits": 1, "first_seen": item.timestamp}))
    by_cam: dict[int, TrackPointOut] = {}
    order: list[int] = []
    for hop in dwells:
        prev = by_cam.get(hop.camera_id)
        if prev is None:
            order.append(hop.camera_id)
            by_cam[hop.camera_id] = hop
            continue
        by_cam[hop.camera_id] = hop.model_copy(
            update={
                "hits": prev.hits + hop.hits,
                "first_seen": prev.first_seen or prev.timestamp,
            }
        )
    return [by_cam[cid] for cid in order]


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
    out = _decorate_track_points(points)
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
    out = _decorate_track_points(points)
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


async def _track_points(
    db: AsyncSession,
    global_track_id: str,
    scoped_to: int | None,
) -> list[TrackPointOut]:
    q = (
        select(TrackPoint)
        .options(selectinload(TrackPoint.camera))
        .where(TrackPoint.global_track_id == global_track_id)
        .order_by(TrackPoint.timestamp.asc())
    )
    points = list((await db.execute(q)).scalars())
    if scoped_to is not None:
        points = [p for p in points if p.camera and p.camera.department_id == scoped_to]
    return _decorate_track_points(points)


@router.post("/face", response_model=FaceSearchOut)
async def search_face(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_capability("search"))],
    purpose: Annotated[str, Form()],
    file: UploadFile = File(...),
    limit: Annotated[int, Form()] = 50,
):
    purpose = validate_purpose(purpose)
    data = await file.read()
    if not data or len(data) > 8 * 1024 * 1024:
        raise HTTPException(400, "Upload a still under 8 MB")
    try:
        hit = embed_image_bytes(data)
    except FaceEngineError as exc:
        raise HTTPException(503, str(exc)) from exc
    if not hit:
        raise HTTPException(400, "No usable face in that still")
    probe, meta = hit
    scoped_to = await department_scope(user)

    people = list(
        (
            await db.execute(
                select(WatchlistEntry).where(
                    WatchlistEntry.is_active.is_(True),
                    WatchlistEntry.entity_type == "person",
                )
            )
        ).scalars()
    )
    wl_hits: list[FaceWatchlistHit] = []
    for entry in people:
        if not entry.face_embedding:
            continue
        extra = entry.extra or {}
        if extra.get("no_face"):
            continue
        try:
            if extra.get("age") is not None and int(extra["age"]) < 21:
                continue
        except (TypeError, ValueError):
            pass
        score = cosine_score(probe, entry.face_embedding)
        if score >= MATCH_THRESHOLD:
            wl_hits.append(
                FaceWatchlistHit(
                    id=entry.id,
                    name=entry.name,
                    category=entry.category,
                    score=round(score, 4),
                    photo_url=entry.photo_url,
                    priority=entry.priority,
                )
            )
    wl_hits.sort(key=lambda h: h.score, reverse=True)

    ev_q = select(DetectionEvent).where(DetectionEvent.object_type == "person")
    ev_q = _apply_dept_scope(ev_q, scoped_to)
    ev_q = ev_q.order_by(DetectionEvent.timestamp.desc()).limit(400)
    recent = list((await db.execute(ev_q)).scalars())
    scored: list[tuple[float, DetectionEvent]] = []
    for ev in recent:
        if not is_face_embedding(ev.embedding):
            continue
        score = cosine_score(probe, ev.embedding)
        if score >= MATCH_THRESHOLD:
            scored.append((score, ev))
    scored.sort(key=lambda pair: pair[0], reverse=True)
    top_events = [ev for _, ev in scored[: max(1, min(limit, 50))]]

    track: list[TrackPointOut] = []
    gid = top_events[0].global_track_id if top_events else None
    if gid:
        track = await _track_points(db, gid, scoped_to)

    await _audit_search(
        db,
        user,
        request,
        "search_face",
        "search/face",
        {
            "purpose": purpose,
            "engine": meta.get("engine"),
            "watchlist_hits": len(wl_hits),
            "event_hits": len(top_events),
        },
    )
    await db.commit()
    return FaceSearchOut(
        engine=str(meta.get("engine") or "unknown"),
        query_has_face=True,
        threshold=MATCH_THRESHOLD,
        watchlist=wl_hits[:10],
        events=[EventOut.model_validate(ev) for ev in top_events],
        track=track,
        global_track_id=gid,
    )

from io import BytesIO
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from app.core.audit import write_audit
from app.core.plates import normalize_plate
from app.core.policy import require_capability
from app.core.security import client_ip, get_current_user
from app.db import get_db
from app.models.user import User
from app.models.watchlist import WatchlistEntry
from app.schemas.common import WatchlistCreate, WatchlistOut
from app.services.face import FaceEngineError, embed_image_bytes
from app.services.storage import save_snapshot_png

router = APIRouter(prefix="/watchlist", tags=["watchlist"])
MAX_FACE_BYTES = 8 * 1024 * 1024


def watchlist_out(entry: WatchlistEntry) -> WatchlistOut:
    item = WatchlistOut.model_validate(entry)
    item.has_face = bool(entry.face_embedding)
    item.photo_url = entry.photo_url
    return item


def _face_enroll_blocked(entry: WatchlistEntry) -> str | None:
    extra = entry.extra or {}
    if extra.get("no_face"):
        return "Face enroll is disabled for this record"
    age = extra.get("age")
    try:
        if age is not None and int(age) < 21:
            return "Face enroll is not allowed for minors"
    except (TypeError, ValueError):
        pass
    return None


@router.get("", response_model=list[WatchlistOut])
async def list_watchlist(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
    category: str | None = None,
    entity_type: str | None = None,
    q: str | None = None,
):
    stmt = select(WatchlistEntry).where(WatchlistEntry.is_active.is_(True))
    if category:
        stmt = stmt.where(WatchlistEntry.category == category)
    if entity_type:
        stmt = stmt.where(WatchlistEntry.entity_type == entity_type)
    if q:
        like = f"%{q}%"
        stmt = stmt.where(
            (WatchlistEntry.plate_number.ilike(like))
            | (WatchlistEntry.name.ilike(like))
            | (WatchlistEntry.description.ilike(like))
        )
    rows = list((await db.execute(stmt.order_by(WatchlistEntry.id.desc()))).scalars())
    await write_audit(
        db,
        user_id=user.id,
        username=user.username,
        action="search_watchlist",
        resource="watchlist",
        details={"q": q, "category": category},
        ip_address=client_ip(request),
    )
    await db.commit()
    return [watchlist_out(row) for row in rows]


@router.post("", response_model=WatchlistOut)
async def add_watchlist(
    payload: WatchlistCreate,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_capability("watchlist_write"))],
):
    entry = WatchlistEntry(
        **payload.model_dump(),
        plate_normalized=normalize_plate(payload.plate_number),
        created_by=user.username,
    )
    db.add(entry)
    await write_audit(
        db,
        user_id=user.id,
        username=user.username,
        action="create_watchlist",
        resource="watchlist",
        details={"plate": payload.plate_number, "category": payload.category},
        ip_address=client_ip(request),
    )
    await db.commit()
    await db.refresh(entry)
    return watchlist_out(entry)


@router.post("/{entry_id}/face", response_model=WatchlistOut)
async def enroll_face(
    entry_id: int,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_capability("watchlist_write"))],
    file: UploadFile = File(...),
):
    entry = await db.get(WatchlistEntry, entry_id)
    if not entry or not entry.is_active:
        raise HTTPException(404, "Not found")
    if entry.entity_type != "person":
        raise HTTPException(400, "Face enroll is only for person records")
    blocked = _face_enroll_blocked(entry)
    if blocked:
        raise HTTPException(400, blocked)
    data = await file.read()
    if not data or len(data) > MAX_FACE_BYTES:
        raise HTTPException(400, "Upload a still under 8 MB")
    try:
        hit = embed_image_bytes(data)
    except FaceEngineError as exc:
        raise HTTPException(503, str(exc)) from exc
    if not hit:
        raise HTTPException(400, "No usable face in that still")
    vec, meta = hit
    try:
        from PIL import Image

        buf = BytesIO()
        Image.open(BytesIO(data)).convert("RGB").save(buf, format="PNG")
        png = buf.getvalue()
    except Exception:
        png = data
    entry.face_embedding = vec
    entry.photo_url = save_snapshot_png(png, prefix=f"face-{entry.id}")
    extra = dict(entry.extra or {})
    extra["face_engine"] = meta.get("engine")
    extra["face_det_score"] = meta.get("det_score")
    entry.extra = extra
    flag_modified(entry, "extra")
    await write_audit(
        db,
        user_id=user.id,
        username=user.username,
        action="enroll_watchlist_face",
        resource=f"watchlist/{entry_id}",
        details={"engine": meta.get("engine"), "name": entry.name},
        ip_address=client_ip(request),
    )
    await db.commit()
    await db.refresh(entry)
    return watchlist_out(entry)


@router.delete("/{entry_id}")
async def deactivate(
    entry_id: int,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_capability("watchlist_write"))],
):
    entry = await db.get(WatchlistEntry, entry_id)
    if not entry:
        raise HTTPException(404, "Not found")
    entry.is_active = False
    await write_audit(
        db,
        user_id=user.id,
        username=user.username,
        action="deactivate_watchlist",
        resource=f"watchlist/{entry_id}",
        ip_address=client_ip(request),
    )
    await db.commit()
    return {"ok": True}

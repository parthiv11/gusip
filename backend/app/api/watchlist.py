from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import write_audit
from app.core.policy import require_capability
from app.core.security import client_ip, get_current_user
from app.db import get_db
from app.models.user import User
from app.models.watchlist import WatchlistEntry
from app.schemas.common import WatchlistCreate, WatchlistOut

router = APIRouter(prefix="/watchlist", tags=["watchlist"])


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
    return rows


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
    return entry


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

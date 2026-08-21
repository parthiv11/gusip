from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import write_audit
from app.core.break_glass import department_scope
from app.core.policy import assert_department_allowed
from app.core.security import client_ip, get_current_user
from app.db import get_db
from app.models.user import User
from app.schemas.common import GapZone
from app.services.gis import cameras_geojson, gap_analysis, nearby_cameras

router = APIRouter(prefix="/gis", tags=["gis"])


@router.get("/cameras")
async def geo_cameras(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
    department_id: int | None = None,
    status: str | None = None,
):
    scoped_to = await department_scope(user)
    if department_id:
        assert_department_allowed(user, department_id, scoped_to)
        data = await cameras_geojson(db, department_id=department_id, status=status)
    else:
        data = await cameras_geojson(db, department_id=scoped_to, status=status)
    await write_audit(
        db,
        user_id=user.id,
        username=user.username,
        action="view_gis",
        resource="gis/cameras",
        ip_address=client_ip(request),
    )
    await db.commit()
    return data


@router.get("/gaps", response_model=list[GapZone])
async def gaps(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
):
    zones = await gap_analysis(db)
    await write_audit(
        db,
        user_id=user.id,
        username=user.username,
        action="gap_analysis",
        resource="gis/gaps",
        ip_address=client_ip(request),
    )
    await db.commit()
    return zones


@router.get("/nearby")
async def nearby(
    db: Annotated[AsyncSession, Depends(get_db)],
    _user: Annotated[User, Depends(get_current_user)],
    lat: float = Query(...),
    lon: float = Query(...),
    radius_m: float = 2000,
):
    return await nearby_cameras(db, lon, lat, radius_m)

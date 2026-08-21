from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.audit import write_audit
from app.core.break_glass import department_scope
from app.core.policy import assert_department_allowed, require_capability
from app.core.security import client_ip, get_current_user
from app.db import get_db
from app.models.camera import Camera, Department
from app.models.user import User
from app.schemas.common import CameraCreate, CameraOut, DepartmentOut
from app.services.event_bus import bus
from geoalchemy2.elements import WKTElement

router = APIRouter(prefix="/cameras", tags=["cameras"])


@router.get("/departments", response_model=list[DepartmentOut])
async def list_departments(
    db: Annotated[AsyncSession, Depends(get_db)],
    _user: Annotated[User, Depends(get_current_user)],
):
    result = await db.execute(select(Department).order_by(Department.name))
    return list(result.scalars())


@router.get("", response_model=list[CameraOut])
async def list_cameras(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
    department_id: int | None = None,
    status: str | None = None,
    source_type: str | None = None,
    city: str | None = None,
    camera_type: str | None = None,
):
    q = select(Camera).options(selectinload(Camera.department)).where(Camera.is_active.is_(True))
    scoped_to = await department_scope(user)
    if department_id:
        assert_department_allowed(user, department_id, scoped_to)
        q = q.where(Camera.department_id == department_id)
    elif scoped_to:
        q = q.where(Camera.department_id == scoped_to)
    if status:
        q = q.where(Camera.status == status)
    if source_type:
        q = q.where(Camera.source_type == source_type)
    if city:
        q = q.where(Camera.city == city)
    if camera_type:
        q = q.where(Camera.camera_type == camera_type)
    result = await db.execute(q.order_by(Camera.code))
    cameras = list(result.scalars())
    await write_audit(
        db,
        user_id=user.id,
        username=user.username,
        action="list_cameras",
        resource="cameras",
        details={"count": len(cameras), "filters": {"department_id": department_id, "status": status}},
        ip_address=client_ip(request),
        department_id=user.department_id,
    )
    await db.commit()
    return cameras


@router.get("/{camera_id}", response_model=CameraOut)
async def get_camera(
    camera_id: int,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
):
    result = await db.execute(
        select(Camera).options(selectinload(Camera.department)).where(Camera.id == camera_id)
    )
    cam = result.scalar_one_or_none()
    if not cam:
        raise HTTPException(404, "Camera not found")
    scoped_to = await department_scope(user)
    assert_department_allowed(user, cam.department_id, scoped_to)
    await write_audit(
        db,
        user_id=user.id,
        username=user.username,
        action="view_camera",
        resource=f"cameras/{cam.code}",
        ip_address=client_ip(request),
    )
    await db.commit()
    return cam


@router.post("", response_model=CameraOut)
async def create_camera(
    payload: CameraCreate,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_capability("onboard_camera"))],
):
    scoped_to = await department_scope(user)
    if scoped_to and payload.department_id != scoped_to:
        raise HTTPException(403, "Can only onboard cameras in your department")
    cam = Camera(
        **payload.model_dump(exclude={"latitude", "longitude"}),
        latitude=payload.latitude,
        longitude=payload.longitude,
        location=WKTElement(f"POINT({payload.longitude} {payload.latitude})", srid=4326),
    )
    db.add(cam)
    await write_audit(
        db,
        user_id=user.id,
        username=user.username,
        action="onboard_camera",
        resource=f"cameras/{payload.code}",
        ip_address=client_ip(request),
    )
    await db.commit()
    await db.refresh(cam)
    return cam


@router.post("/bulk", response_model=dict)
async def bulk_onboard(
    items: list[CameraCreate],
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_capability("onboard_camera"))],
):
    if user.role != "system_admin":
        raise HTTPException(403, "Admin only")
    created = 0
    for payload in items:
        exists = await db.execute(select(Camera.id).where(Camera.code == payload.code))
        if exists.scalar_one_or_none():
            continue
        db.add(
            Camera(
                **payload.model_dump(exclude={"latitude", "longitude"}),
                latitude=payload.latitude,
                longitude=payload.longitude,
                location=WKTElement(f"POINT({payload.longitude} {payload.latitude})", srid=4326),
            )
        )
        created += 1
    await write_audit(
        db,
        user_id=user.id,
        username=user.username,
        action="bulk_onboard",
        resource="cameras",
        details={"created": created},
        ip_address=client_ip(request),
    )
    await db.commit()
    return {"created": created}


@router.get("/{camera_id}/live")
async def camera_live(
    camera_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> dict[str, Any]:
    cam = await db.get(Camera, camera_id)
    if not cam:
        raise HTTPException(404, "Camera not found")
    scoped_to = await department_scope(user)
    assert_department_allowed(user, cam.department_id, scoped_to)
    live = await bus.get_json(f"live:{camera_id}")
    return {
        "camera": {
            "id": cam.id,
            "code": cam.code,
            "name": cam.name,
            "status": cam.status,
            "source_type": cam.source_type,
            "vendor": cam.vendor,
            "city": cam.city,
        },
        "live": live,
        "feed_mode": "metadata_overlay",  # full frames stay at source VMS (NFR-6)
    }

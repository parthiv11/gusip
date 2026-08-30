from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.break_glass import department_scope
from app.core.audit import write_audit
from app.core.crypto import decrypt_bytes
from app.core.policy import assert_department_allowed
from app.core.security import client_ip, get_current_user
from app.db import get_db
from app.models.camera import Camera
from app.models.event import DetectionEvent
from app.models.user import User
from app.services.storage import DATA_DIR

router = APIRouter(prefix="/evidence", tags=["evidence"])


@router.get("/snapshots/{name}")
async def get_snapshot(
    name: str,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
):
    if "/" in name or ".." in name:
        raise HTTPException(400, "Invalid name")
    path = DATA_DIR / "snapshots" / name
    if not path.exists():
        raise HTTPException(404, "Not found")
    expected_url = f"/api/v1/evidence/snapshots/{name}"
    event = await db.scalar(
        select(DetectionEvent)
        .join(Camera, Camera.id == DetectionEvent.camera_id)
        .where(DetectionEvent.snapshot_url == expected_url)
    )
    if event is None:
        raise HTTPException(404, "Evidence manifest not found")
    camera = await db.get(Camera, event.camera_id)
    if camera is None:
        raise HTTPException(404, "Camera not found")
    assert_department_allowed(user, camera.department_id, await department_scope(user))
    try:
        png = decrypt_bytes(path.read_bytes())
    except Exception as exc:
        raise HTTPException(500, f"Decrypt failed: {exc}") from exc
    await write_audit(
        db,
        user_id=user.id,
        username=user.username,
        action="decrypt_evidence_snapshot",
        resource=f"evidence/snapshots/{name}",
        details={"event_id": event.id, "camera_id": camera.id},
        ip_address=client_ip(request),
        department_id=camera.department_id,
    )
    await db.commit()
    return Response(content=png, media_type="image/png")

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.audit import write_audit
from app.core.break_glass import department_scope
from app.core.policy import assert_department_allowed, has_capability, require_capability
from app.core.security import client_ip, get_current_user
from app.db import get_db
from app.models.camera import Camera
from app.models.case import Case, CaseEvidence
from app.models.event import Alert, DetectionEvent
from app.models.user import User
from app.schemas.common import CaseCreate, CaseOut

router = APIRouter(prefix="/cases", tags=["cases"])


async def _authorize_case(user: User, case: Case) -> None:
    if case.department_id is None:
        if user.role != "system_admin" and case.created_by != user.username:
            raise HTTPException(403, "Case is outside your department")
        return
    assert_department_allowed(user, case.department_id, await department_scope(user))


@router.get("", response_model=list[CaseOut])
async def list_cases(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
):
    q = select(Case).order_by(Case.created_at.desc())
    scoped_to = await department_scope(user)
    if scoped_to is not None:
        q = q.where(or_(Case.department_id == scoped_to, Case.created_by == user.username))
    result = await db.execute(q)
    return list(result.scalars())


@router.post("", response_model=CaseOut)
async def create_case(
    payload: CaseCreate,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_capability("create_case"))],
):
    case = Case(
        title=payload.title,
        description=payload.description,
        created_by=user.username,
        department_id=user.department_id,
    )
    db.add(case)
    await write_audit(
        db,
        user_id=user.id,
        username=user.username,
        action="create_case",
        resource="cases",
        details={"title": payload.title},
        ip_address=client_ip(request),
        department_id=case.department_id,
    )
    await db.commit()
    await db.refresh(case)
    return case


@router.post("/{case_id}/evidence")
async def add_evidence(
    case_id: int,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_capability("create_case"))],
    event_id: int | None = None,
    alert_id: int | None = None,
    notes: str | None = None,
):
    case = await db.get(Case, case_id)
    if not case:
        raise HTTPException(404, "Case not found")
    await _authorize_case(user, case)
    if event_id is None and alert_id is None:
        raise HTTPException(400, "event_id or alert_id is required")
    evidence_department: int | None = None
    if event_id is not None:
        event = await db.get(DetectionEvent, event_id)
        if event is None:
            raise HTTPException(404, "Detection event not found")
        event_camera = await db.get(Camera, event.camera_id)
        if event_camera is None:
            raise HTTPException(404, "Event camera not found")
        evidence_department = event_camera.department_id
    if alert_id is not None:
        alert = await db.get(Alert, alert_id)
        if alert is None:
            raise HTTPException(404, "Alert not found")
        alert_camera = await db.get(Camera, alert.camera_id)
        if alert_camera is None:
            raise HTTPException(404, "Alert camera not found")
        if evidence_department is not None and evidence_department != alert_camera.department_id:
            raise HTTPException(400, "Evidence items belong to different departments")
        evidence_department = alert_camera.department_id
    assert_department_allowed(user, evidence_department, await department_scope(user))
    if case.department_id is not None and evidence_department != case.department_id:
        raise HTTPException(403, "Evidence is outside the case department")
    ev = CaseEvidence(case_id=case_id, event_id=event_id, alert_id=alert_id, notes=notes)
    db.add(ev)
    await write_audit(
        db,
        user_id=user.id,
        username=user.username,
        action="add_evidence",
        resource=f"cases/{case_id}",
        ip_address=client_ip(request),
        department_id=case.department_id,
    )
    await db.commit()
    return {"ok": True, "evidence_id": ev.id}


@router.get("/{case_id}/export")
async def export_case(
    case_id: int,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
):
    if not has_capability(user, "export"):
        raise HTTPException(403, "Your role cannot export case files")
    result = await db.execute(select(Case).options(selectinload(Case.evidence)).where(Case.id == case_id))
    case = result.scalar_one_or_none()
    if not case:
        raise HTTPException(404, "Case not found")
    await _authorize_case(user, case)
    await write_audit(
        db,
        user_id=user.id,
        username=user.username,
        action="export_case",
        resource=f"cases/{case_id}",
        ip_address=client_ip(request),
        department_id=case.department_id,
    )
    await db.commit()
    return {
        "case": {
            "id": case.id,
            "title": case.title,
            "description": case.description,
            "status": case.status,
            "created_by": case.created_by,
            "created_at": case.created_at.isoformat(),
        },
        "evidence": [
            {
                "id": e.id,
                "event_id": e.event_id,
                "alert_id": e.alert_id,
                "notes": e.notes,
                "created_at": e.created_at.isoformat(),
            }
            for e in case.evidence
        ],
        "export_format": "json+clips",
    }

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.audit import write_audit
from app.core.policy import has_capability, require_capability
from app.core.security import client_ip, get_current_user
from app.db import get_db
from app.models.case import Case, CaseEvidence
from app.models.user import User
from app.schemas.common import CaseCreate, CaseOut

router = APIRouter(prefix="/cases", tags=["cases"])


@router.get("", response_model=list[CaseOut])
async def list_cases(
    db: Annotated[AsyncSession, Depends(get_db)],
    _user: Annotated[User, Depends(get_current_user)],
):
    result = await db.execute(select(Case).order_by(Case.created_at.desc()))
    return list(result.scalars())


@router.post("", response_model=CaseOut)
async def create_case(
    payload: CaseCreate,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_capability("create_case"))],
):
    case = Case(title=payload.title, description=payload.description, created_by=user.username)
    db.add(case)
    await write_audit(
        db,
        user_id=user.id,
        username=user.username,
        action="create_case",
        resource="cases",
        details={"title": payload.title},
        ip_address=client_ip(request),
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
    ev = CaseEvidence(case_id=case_id, event_id=event_id, alert_id=alert_id, notes=notes)
    db.add(ev)
    await write_audit(
        db,
        user_id=user.id,
        username=user.username,
        action="add_evidence",
        resource=f"cases/{case_id}",
        ip_address=client_ip(request),
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
    await write_audit(
        db,
        user_id=user.id,
        username=user.username,
        action="export_case",
        resource=f"cases/{case_id}",
        ip_address=client_ip(request),
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

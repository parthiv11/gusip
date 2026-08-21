from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import write_audit
from app.core.break_glass import department_scope, get_grant, grant_break_glass, revoke_break_glass
from app.core.policy import PURPOSES, capabilities_for, has_capability
from app.core.security import (
    client_ip,
    create_access_token,
    get_current_user,
    hash_password,
    verify_password,
)
from app.db import get_db
from app.models.user import User
from app.schemas.common import BreakGlassOut, BreakGlassRequest, SessionOut, Token, UserOut

router = APIRouter(prefix="/auth", tags=["auth"])


def _scope_label(scoped_to: int | None) -> str:
    return "department" if scoped_to is not None else "statewide"


def _break_glass_out(grant: dict | None) -> BreakGlassOut | None:
    if not grant:
        return None
    return BreakGlassOut(
        active=True,
        reason=str(grant.get("reason") or ""),
        granted_at=str(grant.get("granted_at") or ""),
        expires_at=str(grant.get("expires_at") or ""),
        duration_minutes=int(grant.get("duration_minutes") or 0),
        home_department_id=grant.get("home_department_id"),
    )


async def session_fields(user: User) -> dict:
    scoped = await department_scope(user)
    grant = await get_grant(user.id)
    return {
        "capabilities": capabilities_for(user.role),
        "scope": _scope_label(scoped),
        "break_glass": _break_glass_out(grant),
        "purposes": list(PURPOSES),
    }


@router.post("/token", response_model=Token)
async def login(
    request: Request,
    form: Annotated[OAuth2PasswordRequestForm, Depends()],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    result = await db.execute(select(User).where(User.username == form.username))
    user = result.scalar_one_or_none()
    if not user or not verify_password(form.password, user.hashed_password) or not user.is_active:
        raise HTTPException(status_code=401, detail="Incorrect username or password")
    token = create_access_token(user.username, user.role, user.department_id)
    await write_audit(
        db,
        user_id=user.id,
        username=user.username,
        action="login",
        resource="auth",
        ip_address=client_ip(request),
        department_id=user.department_id,
    )
    await db.commit()
    extra = await session_fields(user)
    return Token(
        access_token=token,
        role=user.role,
        username=user.username,
        full_name=user.full_name,
        department_id=user.department_id,
        capabilities=extra["capabilities"],
        scope=extra["scope"],
    )


@router.get("/me", response_model=SessionOut)
async def me(user: Annotated[User, Depends(get_current_user)]):
    extra = await session_fields(user)
    return SessionOut(
        id=user.id,
        username=user.username,
        full_name=user.full_name,
        email=user.email,
        role=user.role,
        department_id=user.department_id,
        is_active=user.is_active,
        capabilities=extra["capabilities"],
        scope=extra["scope"],
        break_glass=extra["break_glass"],
        purposes=extra["purposes"],
    )


@router.post("/break-glass", response_model=BreakGlassOut)
async def request_break_glass(
    payload: BreakGlassRequest,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
):
    grant = await grant_break_glass(user, reason=payload.reason, duration_minutes=payload.duration_minutes)
    await write_audit(
        db,
        user_id=user.id,
        username=user.username,
        action="break_glass_grant",
        resource="auth/break-glass",
        details={
            "reason": grant["reason"],
            "duration_minutes": grant["duration_minutes"],
            "expires_at": grant["expires_at"],
        },
        ip_address=client_ip(request),
        department_id=user.department_id,
    )
    await db.commit()
    out = _break_glass_out(grant)
    assert out is not None
    return out


@router.delete("/break-glass")
async def end_break_glass(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
):
    had = await revoke_break_glass(user.id)
    await write_audit(
        db,
        user_id=user.id,
        username=user.username,
        action="break_glass_revoke",
        resource="auth/break-glass",
        details={"had_grant": had},
        ip_address=client_ip(request),
        department_id=user.department_id,
    )
    await db.commit()
    return {"ok": True, "revoked": had}


@router.post("/users", response_model=UserOut)
async def create_user(
    request: Request,
    payload: dict,
    db: Annotated[AsyncSession, Depends(get_db)],
    admin: Annotated[User, Depends(get_current_user)],
):
    if not has_capability(admin, "create_user"):
        raise HTTPException(status_code=403, detail="Admin only")
    user = User(
        username=payload["username"],
        full_name=payload.get("full_name", payload["username"]),
        email=payload["email"],
        hashed_password=hash_password(payload["password"]),
        role=payload.get("role", "control_room_operator"),
        department_id=payload.get("department_id"),
        is_active=True,
        created_at=datetime.now(timezone.utc),
    )
    db.add(user)
    await write_audit(
        db,
        user_id=admin.id,
        username=admin.username,
        action="create_user",
        resource=f"users/{user.username}",
        ip_address=client_ip(request),
    )
    await db.commit()
    await db.refresh(user)
    return user

from datetime import datetime, timezone
import base64
import hashlib
import secrets
from typing import Annotated
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import RedirectResponse
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import write_audit
from app.core.break_glass import department_scope, get_grant, grant_break_glass, revoke_break_glass
from app.core.policy import PURPOSES, capabilities_for, has_capability
from app.core.security import (
    client_ip,
    create_access_token,
    decode_access_token,
    get_current_user,
    hash_password,
    verify_password,
)
from app.db import get_db
from app.config import get_settings
from app.models.user import User
from app.schemas.common import BreakGlassOut, BreakGlassRequest, SessionOut, Token, UserOut

router = APIRouter(prefix="/auth", tags=["auth"])
settings = get_settings()


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


def _set_session_cookies(response: Response, token: str) -> None:
    response.set_cookie(
        key=settings.session_cookie_name,
        value=token,
        max_age=settings.access_token_expire_minutes * 60,
        httponly=True,
        secure=settings.session_cookie_secure,
        samesite="strict",
        path="/",
    )
    response.set_cookie(
        key=settings.csrf_cookie_name,
        value=secrets.token_urlsafe(32),
        max_age=settings.access_token_expire_minutes * 60,
        httponly=False,
        secure=settings.session_cookie_secure,
        samesite="strict",
        path="/",
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
    response: Response,
    form: Annotated[OAuth2PasswordRequestForm, Depends()],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    if not settings.local_auth_enabled:
        raise HTTPException(status_code=404, detail="Local authentication is disabled")
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
    _set_session_cookies(response, token)
    extra = await session_fields(user)
    return Token(
        access_token="" if settings.app_env.lower() in {"production", "prod"} else token,
        role=user.role,
        username=user.username,
        full_name=user.full_name,
        department_id=user.department_id,
        capabilities=extra["capabilities"],
        scope=extra["scope"],
    )


@router.get("/oidc/login")
async def oidc_login():
    if settings.auth_provider != "oidc":
        raise HTTPException(404, "OIDC authentication is not enabled")
    state = secrets.token_urlsafe(32)
    nonce = secrets.token_urlsafe(32)
    verifier = secrets.token_urlsafe(64)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    params = urlencode(
        {
            "client_id": settings.oidc_client_id,
            "response_type": "code",
            "scope": "openid profile email",
            "redirect_uri": settings.oidc_redirect_uri,
            "state": state,
            "nonce": nonce,
            "code_challenge": challenge,
            "code_challenge_method": "S256",
        }
    )
    response = RedirectResponse(f"{settings.oidc_authorization_url}?{params}", status_code=302)
    for name, value in {
        "gusip_oidc_state": state,
        "gusip_oidc_nonce": nonce,
        "gusip_oidc_verifier": verifier,
    }.items():
        response.set_cookie(
            name,
            value,
            max_age=300,
            httponly=True,
            secure=settings.session_cookie_secure,
            samesite="lax",
            path="/api/v1/auth/oidc",
        )
    return response


@router.get("/oidc/callback")
async def oidc_callback(
    request: Request,
    code: str,
    state: str,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    if settings.auth_provider != "oidc" or not secrets.compare_digest(
        state,
        request.cookies.get("gusip_oidc_state", ""),
    ):
        raise HTTPException(401, "Invalid OIDC state")
    verifier = request.cookies.get("gusip_oidc_verifier")
    nonce = request.cookies.get("gusip_oidc_nonce")
    if not verifier or not nonce:
        raise HTTPException(401, "Expired OIDC transaction")
    form = {
        "grant_type": "authorization_code",
        "client_id": settings.oidc_client_id,
        "redirect_uri": settings.oidc_redirect_uri,
        "code": code,
        "code_verifier": verifier,
    }
    if settings.oidc_client_secret:
        form["client_secret"] = settings.oidc_client_secret
    async with httpx.AsyncClient(timeout=15.0, follow_redirects=False) as client:
        token_response = await client.post(settings.oidc_token_url, data=form)
        token_response.raise_for_status()
        tokens = token_response.json()
    access_token = tokens.get("access_token")
    id_token = tokens.get("id_token")
    if not isinstance(access_token, str) or not isinstance(id_token, str):
        raise HTTPException(502, "OIDC provider returned an incomplete token response")
    claims = await decode_access_token(id_token)
    if not secrets.compare_digest(str(claims.get("nonce") or ""), nonce):
        raise HTTPException(401, "Invalid OIDC nonce")
    username = claims.get(settings.oidc_username_claim)
    user = await db.scalar(select(User).where(User.username == username, User.is_active.is_(True)))
    if user is None:
        raise HTTPException(403, "OIDC identity is not provisioned for GUSIP")
    await write_audit(
        db,
        user_id=user.id,
        username=user.username,
        action="oidc_login",
        resource="auth",
        ip_address=client_ip(request),
        department_id=user.department_id,
    )
    await db.commit()
    response = RedirectResponse("/", status_code=302)
    _set_session_cookies(response, access_token)
    for name in ("gusip_oidc_state", "gusip_oidc_nonce", "gusip_oidc_verifier"):
        response.delete_cookie(name, path="/api/v1/auth/oidc")
    return response


@router.post("/logout", status_code=204)
async def logout(response: Response):
    response.delete_cookie(
        key=settings.session_cookie_name,
        path="/",
        secure=settings.session_cookie_secure,
        httponly=True,
        samesite="strict",
    )
    response.delete_cookie(
        key=settings.csrf_cookie_name,
        path="/",
        secure=settings.session_cookie_secure,
        samesite="strict",
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

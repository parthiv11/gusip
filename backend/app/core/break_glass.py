"""Time-boxed break-glass grants (CISA ICAM / zero-trust exception path).

Stored in Redis with TTL so access dies even if the operator forgets to revoke.
Every grant and revoke is audited separately from routine camera views.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import HTTPException, status

from app.models.user import User
from app.services.event_bus import bus

MIN_REASON_LEN = 16
MAX_MINUTES = 120
DEFAULT_MINUTES = 30


def _key(user_id: int) -> str:
    return f"breakglass:{user_id}"


async def get_grant(user_id: int) -> dict[str, Any] | None:
    try:
        data = await bus.get_json(_key(user_id))
    except RuntimeError:
        return None
    return data if isinstance(data, dict) else None


async def department_scope(user: User) -> int | None:
    """None = statewide. Otherwise filter cameras/events to this department."""
    from app.core.policy import is_home_scoped

    if not is_home_scoped(user):
        return None
    if await get_grant(user.id):
        return None
    return user.department_id


async def grant_break_glass(
    user: User,
    *,
    reason: str,
    duration_minutes: int | None,
) -> dict[str, Any]:
    from app.core.policy import has_capability, is_home_scoped

    if not has_capability(user, "break_glass"):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Your role cannot request break-glass")
    if not is_home_scoped(user):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "Your role already has statewide camera access",
        )
    text = (reason or "").strip()
    if len(text) < MIN_REASON_LEN:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"Break-glass reason must be at least {MIN_REASON_LEN} characters (FIR / incident reference)",
        )
    minutes = duration_minutes or DEFAULT_MINUTES
    if minutes < 5 or minutes > MAX_MINUTES:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Duration must be 5–{MAX_MINUTES} minutes")
    now = datetime.now(timezone.utc)
    expires = now + timedelta(minutes=minutes)
    payload = {
        "user_id": user.id,
        "username": user.username,
        "reason": text,
        "home_department_id": user.department_id,
        "granted_at": now.isoformat(),
        "expires_at": expires.isoformat(),
        "duration_minutes": minutes,
    }
    await bus.set_json(_key(user.id), payload, ttl=minutes * 60)
    return payload


async def revoke_break_glass(user_id: int) -> bool:
    existing = await get_grant(user_id)
    try:
        await bus.delete_key(_key(user_id))
    except RuntimeError:
        return False
    return bool(existing)

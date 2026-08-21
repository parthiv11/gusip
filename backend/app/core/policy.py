"""RBAC on the surface, ABAC underneath (NIST SP 800-162 / ANSI INCITS 359).

Operators still pick one of four roles. Enforcement uses role + department +
action + investigation purpose + optional time-boxed break-glass.
"""

from __future__ import annotations

from typing import Annotated, Iterable

from fastapi import Depends, HTTPException, status

from app.core.security import get_current_user
from app.models.user import User

PURPOSES: tuple[str, ...] = (
    "stolen_vehicle",
    "blacklisted_vehicle",
    "wanted_person",
    "missing_person",
    "traffic_incident",
    "law_and_order",
    "evaluation",
)

# Visible roles stay at four. Capabilities are the action dimension of ABAC.
ROLE_CAPABILITIES: dict[str, frozenset[str]] = {
    "control_room_operator": frozenset(
        {"view_live", "ack_alert", "search", "create_case"}
    ),
    "investigation_officer": frozenset(
        {
            "view_live",
            "ack_alert",
            "search",
            "export",
            "watchlist_write",
            "create_case",
            "break_glass",
        }
    ),
    "department_coordinator": frozenset(
        {
            "view_live",
            "ack_alert",
            "search",
            "export",
            "watchlist_write",
            "onboard_camera",
            "admin_stats",
            "create_case",
            "break_glass",
        }
    ),
    "system_admin": frozenset(
        {
            "view_live",
            "ack_alert",
            "search",
            "export",
            "watchlist_write",
            "onboard_camera",
            "admin_stats",
            "create_user",
            "create_case",
            "statewide",
        }
    ),
}

# Home-department filter (organization attribute). SOC operator / IO / admin
# are statewide by default; coordinators are not, unless break-glass is active.
SCOPED_ROLES = frozenset({"department_coordinator"})


def capabilities_for(role: str) -> list[str]:
    caps = set(ROLE_CAPABILITIES.get(role, frozenset()))
    if role == "system_admin":
        caps.update({"statewide"})
    return sorted(caps)


def has_capability(user: User, action: str) -> bool:
    if user.role == "system_admin":
        return True
    return action in ROLE_CAPABILITIES.get(user.role, frozenset())


def require_capability(action: str):
    async def checker(user: Annotated[User, Depends(get_current_user)]) -> User:
        if not has_capability(user, action):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Your role cannot {action.replace('_', ' ')}",
            )
        return user

    return checker


def is_home_scoped(user: User) -> bool:
    return user.role in SCOPED_ROLES and user.department_id is not None


def validate_purpose(purpose: str | None) -> str:
    value = (purpose or "").strip()
    if value not in PURPOSES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Investigation purpose required (stolen_vehicle, wanted_person, evaluation, …)",
        )
    return value


def assert_department_allowed(user: User, department_id: int | None, scoped_to: int | None) -> None:
    if scoped_to is None or department_id is None:
        return
    if department_id != scoped_to:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Camera is outside your department. Request time-boxed break-glass access.",
        )

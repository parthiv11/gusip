"""RBAC on the surface, ABAC underneath (NIST SP 800-162 / ANSI INCITS 359).

Operators still pick a named role. Enforcement uses role + department +
action + investigation purpose + optional time-boxed break-glass.
Custom roles live in the roles table and are cached for capability checks.
"""

from __future__ import annotations

import re
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

CAPABILITY_CATALOG: tuple[tuple[str, str], ...] = (
    ("view_live", "View live wall, GIS, and cameras"),
    ("ack_alert", "Acknowledge alerts"),
    ("search", "Investigate / search"),
    ("export", "Export reports"),
    ("watchlist_write", "Edit watchlist"),
    ("onboard_camera", "Onboard / sync cameras"),
    ("admin_stats", "Admin stats and audit"),
    ("create_case", "Create case folders"),
    ("break_glass", "Request statewide break-glass"),
    ("statewide", "Statewide cameras (no home-department lock)"),
    ("create_user", "Create user accounts"),
    ("manage_roles", "Super admin: create, assign, and remove roles"),
)

ALL_CAPABILITIES = frozenset(item[0] for item in CAPABILITY_CATALOG)
SUPER_ADMIN_ONLY = frozenset({"create_user", "manage_roles"})

ROLE_LABELS: dict[str, str] = {
    "system_admin": "Super administrator",
    "control_room_operator": "Control room operator",
    "investigation_officer": "Investigation officer",
    "department_coordinator": "Department coordinator",
}

ROLE_CAPABILITIES: dict[str, frozenset[str]] = {
    "control_room_operator": frozenset({"view_live", "ack_alert", "search", "create_case"}),
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
    "system_admin": ALL_CAPABILITIES,
}

BUILTIN_SLUGS = frozenset(ROLE_CAPABILITIES)
SCOPED_ROLES = frozenset({"control_room_operator", "investigation_officer", "department_coordinator"})
SLUG_RE = re.compile(r"^[a-z][a-z0-9_]{1,62}$")

_custom_caps: dict[str, frozenset[str]] = {}
_custom_statewide: set[str] = set()
_custom_names: dict[str, str] = {}


def sanitize_caps(raw: Iterable[str], *, allow_privileged: bool = False) -> list[str]:
    allowed = ALL_CAPABILITIES if allow_privileged else ALL_CAPABILITIES - SUPER_ADMIN_ONLY
    return sorted({item for item in raw if item in allowed})


def register_custom_roles(rows: Iterable[object]) -> None:
    """Replace the custom-role cache. Each row needs slug, capabilities, statewide, name."""
    global _custom_caps, _custom_statewide, _custom_names
    caps: dict[str, frozenset[str]] = {}
    statewide: set[str] = set()
    names: dict[str, str] = {}
    for row in rows:
        slug = str(getattr(row, "slug"))
        if slug in BUILTIN_SLUGS:
            continue
        items = sanitize_caps(getattr(row, "capabilities") or [])
        if getattr(row, "statewide", False) and "statewide" not in items:
            items = sorted({*items, "statewide"})
        caps[slug] = frozenset(items)
        names[slug] = str(getattr(row, "name") or slug)
        if "statewide" in caps[slug]:
            statewide.add(slug)
    _custom_caps = caps
    _custom_statewide = statewide
    _custom_names = names


def known_role_slugs() -> set[str]:
    return set(BUILTIN_SLUGS) | set(_custom_caps)


def role_display_name(slug: str) -> str:
    return ROLE_LABELS.get(slug) or _custom_names.get(slug) or slug.replace("_", " ")


def capabilities_for(role: str) -> list[str]:
    if role == "system_admin":
        return sorted(ALL_CAPABILITIES)
    if role in ROLE_CAPABILITIES:
        return sorted(ROLE_CAPABILITIES[role])
    return sorted(_custom_caps.get(role, frozenset()))


def has_capability(user: User, action: str) -> bool:
    if user.role == "system_admin":
        return True
    return action in capabilities_for(user.role)


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
    if user.department_id is None:
        return False
    return "statewide" not in capabilities_for(user.role)


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


def normalize_role_slug(raw: str) -> str:
    slug = (raw or "").strip().lower().replace(" ", "_")
    if not SLUG_RE.match(slug):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Role id must be lowercase letters, numbers, and underscores (e.g. night_shift_lead)",
        )
    return slug

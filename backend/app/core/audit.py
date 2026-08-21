from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.audit import AuditLog

settings = get_settings()


async def write_audit(
    db: AsyncSession,
    *,
    user_id: int | None,
    username: str | None,
    action: str,
    resource: str,
    details: dict[str, Any] | None = None,
    ip_address: str | None = None,
    department_id: int | None = None,
) -> None:
    if not settings.audit_enabled:
        return
    db.add(
        AuditLog(
            user_id=user_id,
            username=username,
            action=action,
            resource=resource,
            details=details or {},
            ip_address=ip_address,
            department_id=department_id,
            created_at=datetime.now(timezone.utc),
        )
    )
    await db.flush()

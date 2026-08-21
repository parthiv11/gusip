"""Secure stub interfaces for future VAHAN / SARTHI / eGujCop / AFIS / NAFIS (FR-7.4)."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.core.security import require_roles
from app.models.user import User

router = APIRouter(prefix="/integrations", tags=["integrations"])


class LookupRequest(BaseModel):
    plate: str | None = None
    person_id: str | None = None
    source: str


ALLOWED = {"VAHAN", "SARTHI", "eGujCop", "AFIS", "NAFIS"}


@router.post("/lookup")
async def gov_lookup(
    body: LookupRequest,
    user: Annotated[User, Depends(require_roles("system_admin", "investigation_officer"))],
):
    if body.source not in ALLOWED:
        raise HTTPException(400, f"Unknown source. Allowed: {sorted(ALLOWED)}")
    # Intentionally not connected in PoC — returns contract + audit-ready envelope.
    return {
        "connected": False,
        "source": body.source,
        "status": "interface_ready",
        "requested_by": user.username,
        "query": {"plate": body.plate, "person_id": body.person_id},
        "message": (
            f"{body.source} connector is defined (mTLS + signed JWT). "
            "Live government endpoints are not invoked from the PoC environment."
        ),
        "next_step": "Configure department-issued client certificates and IP allowlists.",
    }

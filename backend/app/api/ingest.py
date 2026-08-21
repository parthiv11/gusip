from typing import Annotated, Any

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db import get_db
from app.services.pipeline import ingest_detection

router = APIRouter(prefix="/ingest", tags=["ingest"])
settings = get_settings()


@router.post("/detection")
async def push_detection(
    payload: dict[str, Any],
    db: Annotated[AsyncSession, Depends(get_db)],
    x_adapter_key: str | None = Header(default=None),
):
    """Internal adapter endpoint. Departmental VMS adapters POST normalised detections here."""
    expected = settings.secret_key[:16]
    if x_adapter_key != expected:
        raise HTTPException(401, "Invalid adapter key")
    event = await ingest_detection(db, payload)
    if not event:
        raise HTTPException(404, "Unknown camera")
    return {"event_id": event.id, "global_track_id": event.global_track_id, "alert_checked": True}

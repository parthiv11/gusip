from datetime import datetime, timezone
import hashlib
import hmac
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db import get_db
from app.models.ingest import IngestReceipt
from app.schemas.ingest import DetectionEnvelope
from app.services.pipeline import ingest_detection

router = APIRouter(prefix="/ingest", tags=["ingest"])
settings = get_settings()


@router.post("/detection")
async def push_detection(
    envelope: DetectionEnvelope,
    db: Annotated[AsyncSession, Depends(get_db)],
    x_adapter_signature: str | None = Header(default=None),
):
    """Accept a signed, replay-protected detection from a departmental adapter."""
    key = settings.adapter_key_map.get(envelope.adapter_id)
    supplied = (x_adapter_signature or "").removeprefix("sha256=")
    expected = hmac.new((key or "").encode(), envelope.canonical_bytes(), hashlib.sha256).hexdigest()
    if not key or not hmac.compare_digest(supplied, expected):
        raise HTTPException(401, "Invalid adapter signature")

    issued_at = envelope.issued_at
    if issued_at.tzinfo is None:
        issued_at = issued_at.replace(tzinfo=timezone.utc)
    skew = abs((datetime.now(timezone.utc) - issued_at).total_seconds())
    if skew > settings.ingest_max_clock_skew_seconds:
        raise HTTPException(401, "Expired ingest envelope")

    replay = await db.scalar(
        select(IngestReceipt.id).where(
            IngestReceipt.adapter_id == envelope.adapter_id,
            (IngestReceipt.event_id == str(envelope.event_id)) | (IngestReceipt.sequence == envelope.sequence),
        )
    )
    if replay is not None:
        raise HTTPException(409, "Duplicate ingest envelope")

    db.add(
        IngestReceipt(
            adapter_id=envelope.adapter_id,
            event_id=str(envelope.event_id),
            sequence=envelope.sequence,
            issued_at=issued_at,
        )
    )
    try:
        event = await ingest_detection(db, envelope.payload.model_dump())
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(409, "Duplicate ingest envelope") from exc
    if not event:
        raise HTTPException(404, "Unknown camera")
    return {"event_id": event.id, "global_track_id": event.global_track_id, "alert_checked": True}

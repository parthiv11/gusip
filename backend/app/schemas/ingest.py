from __future__ import annotations

from datetime import datetime
import json
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class DetectionPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    camera_id: int = Field(gt=0)
    timestamp: datetime
    event_type: str = Field(default="detection", min_length=1, max_length=32)
    object_type: str = Field(default="vehicle", min_length=1, max_length=32)
    local_track_id: str | None = Field(default=None, max_length=64)
    plate_number: str | None = Field(default=None, max_length=32)
    confidence: float = Field(default=0.9, ge=0, le=1)
    attributes: dict[str, Any] = Field(default_factory=dict)
    bbox: dict[str, float] = Field(default_factory=dict)
    embedding: list[float] | None = Field(default=None, max_length=4096)


class DetectionEnvelope(BaseModel):
    model_config = ConfigDict(extra="forbid")

    adapter_id: str = Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9._-]+$")
    event_id: UUID
    issued_at: datetime
    sequence: int = Field(ge=0)
    schema_version: Literal["1.0"]
    payload: DetectionPayload

    def canonical_bytes(self) -> bytes:
        value = self.model_dump(mode="json", exclude_none=False, by_alias=True)
        return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()

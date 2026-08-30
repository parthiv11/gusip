from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, field_serializer


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str
    username: str
    full_name: str
    department_id: int | None = None
    capabilities: list[str] = Field(default_factory=list)
    scope: str = "statewide"


class BreakGlassOut(BaseModel):
    active: bool = True
    reason: str
    granted_at: str
    expires_at: str
    duration_minutes: int
    home_department_id: int | None = None


class BreakGlassRequest(BaseModel):
    reason: str = Field(min_length=16, max_length=500)
    duration_minutes: int = Field(default=30, ge=5, le=120)


class UserOut(BaseModel):
    id: int
    username: str
    full_name: str
    email: str
    role: str
    department_id: int | None
    is_active: bool

    model_config = {"from_attributes": True}


class SessionOut(UserOut):
    capabilities: list[str] = Field(default_factory=list)
    scope: str = "statewide"
    break_glass: BreakGlassOut | None = None
    purposes: list[str] = Field(default_factory=list)


class DepartmentOut(BaseModel):
    id: int
    code: str
    name: str
    zone: str

    model_config = {"from_attributes": True}


class CameraCreate(BaseModel):
    code: str
    name: str
    department_id: int
    camera_type: str = "ip"
    ownership: str
    source_type: str
    vendor: str | None = None
    rtsp_url: str | None = None
    onvif_endpoint: str | None = None
    vendor_api_ref: str | None = None
    status: str = "online"
    connectivity: str = "fiber"
    storage_details: str | None = None
    amc_status: str = "active"
    coverage_radius_m: float = 80
    latitude: float
    longitude: float
    city: str
    address: str | None = None
    extra: dict[str, Any] = Field(default_factory=dict)


class CameraOut(BaseModel):
    id: int
    code: str
    name: str
    department_id: int
    camera_type: str
    ownership: str
    source_type: str
    vendor: str | None
    status: str
    connectivity: str
    storage_details: str | None
    amc_status: str
    coverage_radius_m: float
    latitude: float
    longitude: float
    city: str
    address: str | None
    extra: dict[str, Any] = Field(default_factory=dict)
    last_seen_at: datetime | None
    is_active: bool
    department: DepartmentOut | None = None

    model_config = {"from_attributes": True}

    @field_serializer("extra")
    def redact_upstream_media(self, value: dict[str, Any]) -> dict[str, Any]:
        sensitive = {
            "rtsp_url",
            "hls_url",
            "hls_live_url",
            "whep_url",
            "webrtc_url",
            "stream_url",
            "portal",
        }
        return {key: item for key, item in value.items() if key not in sensitive}


class WatchlistCreate(BaseModel):
    entity_type: str
    category: str
    plate_number: str | None = None
    name: str | None = None
    description: str | None = None
    appearance_notes: str | None = None
    extra: dict[str, Any] = Field(default_factory=dict)
    priority: str = "high"


class WatchlistOut(BaseModel):
    id: int
    entity_type: str
    category: str
    plate_number: str | None
    plate_normalized: str | None
    name: str | None
    description: str | None
    appearance_notes: str | None
    extra: dict[str, Any]
    priority: str
    is_active: bool
    created_at: datetime
    photo_url: str | None = None
    has_face: bool = False

    model_config = {"from_attributes": True}


class AlertOut(BaseModel):
    id: int
    event_id: int | None
    watchlist_id: int
    camera_id: int
    timestamp: datetime
    confidence: float
    snapshot_url: str | None
    clip_url: str | None
    status: str
    acknowledged_by: str | None
    acknowledged_at: datetime | None
    notes: str | None
    payload: dict[str, Any]
    camera: CameraOut | None = None
    watchlist: WatchlistOut | None = None

    model_config = {"from_attributes": True}


class EventOut(BaseModel):
    id: int
    camera_id: int
    timestamp: datetime
    event_type: str
    object_type: str
    local_track_id: str | None
    global_track_id: str | None
    plate_number: str | None
    plate_normalized: str | None
    confidence: float
    snapshot_url: str | None
    clip_url: str | None
    attributes: dict[str, Any]
    bbox: dict[str, Any]

    model_config = {"from_attributes": True}


class TrackPointOut(BaseModel):
    id: int
    global_track_id: str
    camera_id: int
    timestamp: datetime
    latitude: float
    longitude: float
    object_type: str
    plate_normalized: str | None
    confidence: float
    camera_code: str | None = None
    camera_name: str | None = None
    city: str | None = None

    model_config = {"from_attributes": True}


class CaseCreate(BaseModel):
    title: str
    description: str | None = None


class CaseOut(BaseModel):
    id: int
    title: str
    description: str | None
    status: str
    created_by: str
    department_id: int | None
    created_at: datetime

    model_config = {"from_attributes": True}


class SearchQuery(BaseModel):
    plate: str | None = None
    object_type: str | None = None
    camera_id: int | None = None
    event_type: str | None = None
    city: str | None = None
    from_ts: datetime | None = None
    to_ts: datetime | None = None
    color: str | None = None
    vehicle_class: str | None = None
    purpose: str
    limit: int = 100


class FaceWatchlistHit(BaseModel):
    id: int
    name: str | None
    category: str
    score: float
    photo_url: str | None = None
    priority: str = "high"


class FaceSearchOut(BaseModel):
    engine: str
    query_has_face: bool
    threshold: float
    watchlist: list[FaceWatchlistHit]
    events: list[EventOut]
    track: list[TrackPointOut]
    global_track_id: str | None = None


class GapZone(BaseModel):
    city: str
    camera_count: int
    uncovered_hint: str
    recommended_cameras: int

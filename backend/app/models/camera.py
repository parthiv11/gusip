from datetime import datetime

from geoalchemy2 import Geography
from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class Department(Base):
    __tablename__ = "departments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(128))
    zone: Mapped[str] = mapped_column(String(64), default="Gujarat")

    cameras = relationship("Camera", back_populates="department")
    users = relationship("User", back_populates="department")


class Camera(Base):
    __tablename__ = "cameras"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(256))
    department_id: Mapped[int] = mapped_column(ForeignKey("departments.id"), index=True)
    camera_type: Mapped[str] = mapped_column(String(32))  # ip | analog
    ownership: Mapped[str] = mapped_column(String(64))
    source_type: Mapped[str] = mapped_column(String(32))  # rtsp | onvif | vendor_api
    vendor: Mapped[str | None] = mapped_column(String(64), nullable=True)
    rtsp_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    onvif_endpoint: Mapped[str | None] = mapped_column(Text, nullable=True)
    vendor_api_ref: Mapped[str | None] = mapped_column(String(128), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="online", index=True)
    connectivity: Mapped[str] = mapped_column(String(32), default="fiber")
    storage_details: Mapped[str | None] = mapped_column(Text, nullable=True)
    amc_status: Mapped[str] = mapped_column(String(32), default="active")
    coverage_radius_m: Mapped[float] = mapped_column(Float, default=80.0)
    location: Mapped[object] = mapped_column(Geography(geometry_type="POINT", srid=4326))
    latitude: Mapped[float] = mapped_column(Float)
    longitude: Mapped[float] = mapped_column(Float)
    city: Mapped[str] = mapped_column(String(64), index=True)
    address: Mapped[str | None] = mapped_column(Text, nullable=True)
    extra: Mapped[dict] = mapped_column(JSONB, default=dict)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    department = relationship("Department", back_populates="cameras")

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class IngestReceipt(Base):
    __tablename__ = "ingest_receipts"
    __table_args__ = (
        UniqueConstraint("adapter_id", "event_id", name="uq_ingest_adapter_event"),
        UniqueConstraint("adapter_id", "sequence", name="uq_ingest_adapter_sequence"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    adapter_id: Mapped[str] = mapped_column(String(64), index=True)
    event_id: Mapped[str] = mapped_column(String(36))
    sequence: Mapped[int] = mapped_column(BigInteger)
    issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

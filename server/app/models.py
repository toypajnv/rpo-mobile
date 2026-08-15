from __future__ import annotations
from datetime import datetime, timezone
from sqlalchemy import String, DateTime, Integer, ForeignKey, Text, Boolean, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Operator(Base):
    __tablename__ = "operators"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ExportBatch(Base):
    __tablename__ = "export_batches"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    period_from: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    period_to: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    recipient: Mapped[str] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(40), default="created")
    event_count: Mapped[int] = mapped_column(Integer, default=0)
    file_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_by_id: Mapped[int] = mapped_column(ForeignKey("operators.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by: Mapped[Operator] = relationship()


class PermitRecord(Base):
    """Canonical one-row representation of a work permit.

    Raw MobileEvent rows remain as an immutable technical audit/sync log, while
    this table is the operator-facing source of truth: one DB row per permit.
    data_json stores the latest value/comment/timestamp for every RPO field.
    """
    __tablename__ = "permit_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    permit_number: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    device_id: Mapped[str] = mapped_column(String(160), index=True)
    worker_name: Mapped[str] = mapped_column(String(180), index=True)
    data_json: Mapped[str] = mapped_column(Text, default="{}")
    first_received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    exported_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    export_batch_id: Mapped[int | None] = mapped_column(ForeignKey("export_batches.id"), nullable=True)
    export_batch: Mapped[ExportBatch | None] = relationship()


class MobileEvent(Base):
    __tablename__ = "mobile_events"
    __table_args__ = (UniqueConstraint("client_event_id", name="uq_mobile_event_client_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    client_event_id: Mapped[str] = mapped_column(String(64), index=True)
    device_id: Mapped[str] = mapped_column(String(160), index=True)
    worker_name: Mapped[str] = mapped_column(String(180), index=True)
    permit_number: Mapped[str] = mapped_column(String(80), index=True)
    field_key: Mapped[str] = mapped_column(String(4), index=True)
    stage_label: Mapped[str] = mapped_column(String(255))
    event_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    field_value: Mapped[str] = mapped_column(Text)
    comment: Mapped[str] = mapped_column(Text, default="")
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    exported_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    export_batch_id: Mapped[int | None] = mapped_column(ForeignKey("export_batches.id"), nullable=True)
    export_batch: Mapped[ExportBatch | None] = relationship()

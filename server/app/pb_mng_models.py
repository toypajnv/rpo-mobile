from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class PbViolationRule(Base):
    __tablename__ = "pb_violation_rules"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    source: Mapped[str] = mapped_column(String(40), index=True)
    number: Mapped[int] = mapped_column(Integer, index=True)
    barrier: Mapped[str] = mapped_column(Text, default="")
    text: Mapped[str] = mapped_column(Text)
    severities_json: Mapped[str] = mapped_column(Text, default="[]")
    criteria_json: Mapped[str] = mapped_column(Text, default="{}")
    requires_context: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class PbStop(Base):
    __tablename__ = "pb_stops"
    __table_args__ = (UniqueConstraint("public_id", name="uq_pb_stop_public_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    public_id: Mapped[str] = mapped_column(String(40), unique=True, index=True)
    device_id: Mapped[str] = mapped_column(String(160), index=True)
    device_token_hash: Mapped[str] = mapped_column(String(64), index=True)

    initiator_name: Mapped[str] = mapped_column(String(240), index=True)
    initiator_unit: Mapped[str] = mapped_column(String(160), default="", index=True)
    initiator_pass: Mapped[str] = mapped_column(String(60), default="", index=True)

    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)

    block: Mapped[str] = mapped_column(String(160), default="", index=True)
    structural_unit: Mapped[str] = mapped_column(String(160), default="", index=True)
    field_name: Mapped[str] = mapped_column(String(180), default="", index=True)
    location: Mapped[str] = mapped_column(String(300), default="")
    contractor: Mapped[str] = mapped_column(String(300), default="", index=True)
    subcontractor: Mapped[str] = mapped_column(String(300), default="")
    work_type: Mapped[str] = mapped_column(String(180), default="", index=True)
    permit_number: Mapped[str] = mapped_column(String(100), default="", index=True)

    violation_id: Mapped[str] = mapped_column(String(80), default="", index=True)
    violation_text: Mapped[str] = mapped_column(Text, default="")
    violation_barrier: Mapped[str] = mapped_column(Text, default="")
    initial_severity: Mapped[str] = mapped_column(String(30), default="", index=True)
    current_severity: Mapped[str] = mapped_column(String(30), default="", index=True)
    severity_context: Mapped[str] = mapped_column(Text, default="")
    description: Mapped[str] = mapped_column(Text, default="")

    responsible_fio: Mapped[str] = mapped_column(String(240), default="")
    responsible_position: Mapped[str] = mapped_column(String(240), default="")
    responsible_pass: Mapped[str] = mapped_column(String(60), default="", index=True)
    crew_json: Mapped[str] = mapped_column(Text, default="[]")
    supervisor_fio: Mapped[str] = mapped_column(String(240), default="")
    supervisor_pass: Mapped[str] = mapped_column(String(60), default="")

    status: Mapped[str] = mapped_column(String(48), default="pending_verification", index=True)
    verification_note: Mapped[str] = mapped_column(Text, default="")
    measures_json: Mapped[str] = mapped_column(Text, default="[]")
    course_name: Mapped[str] = mapped_column(String(300), default="")
    course_status: Mapped[str] = mapped_column(String(40), default="")
    pkm_required: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    pkm_status: Mapped[str] = mapped_column(String(40), default="not_required", index=True)
    pkm_text: Mapped[str] = mapped_column(Text, default="")

    resolution_comment: Mapped[str] = mapped_column(Text, default="")
    resolution_submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    resolution_confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    verified_by_id: Mapped[int | None] = mapped_column(ForeignKey("operators.id"), nullable=True)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    block_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    route_snapshot_json: Mapped[str] = mapped_column(Text, default="{}")
    mail_status: Mapped[str] = mapped_column(String(80), default="not_sent")

    photos: Mapped[list["PbPhoto"]] = relationship(back_populates="stop", cascade="all, delete-orphan")
    actions: Mapped[list["PbAction"]] = relationship(back_populates="stop", cascade="all, delete-orphan")
    restrictions: Mapped[list["PbAccessRestriction"]] = relationship(back_populates="stop", cascade="all, delete-orphan")


class PbPhoto(Base):
    __tablename__ = "pb_photos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    stop_id: Mapped[int] = mapped_column(ForeignKey("pb_stops.id", ondelete="CASCADE"), index=True)
    phase: Mapped[str] = mapped_column(String(32), index=True)
    stored_name: Mapped[str] = mapped_column(String(255), unique=True)
    original_name: Mapped[str] = mapped_column(String(255), default="")
    mime_type: Mapped[str] = mapped_column(String(120), default="image/jpeg")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    stop: Mapped[PbStop] = relationship(back_populates="photos")


class PbAction(Base):
    __tablename__ = "pb_actions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    stop_id: Mapped[int] = mapped_column(ForeignKey("pb_stops.id", ondelete="CASCADE"), index=True)
    actor_type: Mapped[str] = mapped_column(String(30), index=True)
    actor_name: Mapped[str] = mapped_column(String(240), default="")
    action: Mapped[str] = mapped_column(String(80), index=True)
    data_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    stop: Mapped[PbStop] = relationship(back_populates="actions")


class PbAccessRestriction(Base):
    __tablename__ = "pb_access_restrictions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    stop_id: Mapped[int] = mapped_column(ForeignKey("pb_stops.id", ondelete="CASCADE"), index=True)
    pass_number: Mapped[str] = mapped_column(String(60), index=True)
    fio: Mapped[str] = mapped_column(String(240), default="", index=True)
    restriction_kind: Mapped[str] = mapped_column(String(30), default="personnel", index=True)
    reason: Mapped[str] = mapped_column(Text, default="")
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    released_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    released_by_id: Mapped[int | None] = mapped_column(ForeignKey("operators.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    stop: Mapped[PbStop] = relationship(back_populates="restrictions")


class PbEmailRoute(Base):
    __tablename__ = "pb_email_routes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    block: Mapped[str] = mapped_column(String(160), default="", index=True)
    contractor: Mapped[str] = mapped_column(String(300), default="", index=True)
    role: Mapped[str] = mapped_column(String(80), default="", index=True)
    recipient_name: Mapped[str] = mapped_column(String(240), default="")
    email: Mapped[str] = mapped_column(String(320), index=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
from __future__ import annotations

import json
from typing import Literal

from fastapi import Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import MobileEvent, Operator, PermitRecord
from .services.exporter import record_data


class TransmissionReviewRequest(BaseModel):
    decision: Literal["approved", "rejected"]
    reason: str = Field(default="", max_length=500)


def _field_from_event(event: MobileEvent) -> dict:
    return {
        "stage_label": event.stage_label,
        "field_value": event.field_value,
        "event_time": event.event_time.isoformat(),
        "comment": event.comment or "",
        "client_event_id": event.client_event_id,
        "event_id": event.id,
        "approval_required": bool(event.approval_required),
        "approval_status": event.approval_status or "not_required",
        "approved_at": event.approved_at.isoformat() if event.approved_at else "",
        "approved_by_id": event.approved_by_id,
    }


def install_transmission_review(core) -> None:
    """Allow an operator to review every received transmission, including legacy rows.

    Rejection is a data-quality action, not a work prohibition. If the rejected row
    is the current value of a stage, the canonical permit is rolled back to the
    previous non-rejected transmission for that stage (or the stage is removed when
    no earlier value exists).
    """
    if getattr(core, "_transmission_review_installed", False):
        return
    core._transmission_review_installed = True

    @core.app.post("/api/operator/transmissions/{event_id}/review")
    def review_transmission(
        event_id: int,
        payload: TransmissionReviewRequest,
        operator: Operator = Depends(core.current_operator),
        db: Session = Depends(core.get_db),
    ):
        event = db.get(MobileEvent, event_id)
        if not event:
            raise HTTPException(status_code=404, detail="Передача не найдена")

        reason = payload.reason.strip()
        if payload.decision == "rejected" and len(reason) < 3:
            raise HTTPException(status_code=400, detail="Укажите причину отклонения записи")

        decided_at = core.utcnow()
        record = db.scalar(select(PermitRecord).where(PermitRecord.permit_number == event.permit_number))
        data = record_data(record) if record else {}
        current = data.get(event.field_key) if isinstance(data.get(event.field_key), dict) else None
        is_current = bool(current and current.get("client_event_id") == event.client_event_id)
        restored_event_id: int | None = None

        if payload.decision == "rejected":
            event.approval_required = True
            event.approval_status = "rejected"
            event.approved_at = decided_at
            event.approved_by_id = operator.id

            if record and is_current:
                previous = db.scalar(
                    select(MobileEvent)
                    .where(
                        MobileEvent.permit_number == event.permit_number,
                        MobileEvent.field_key == event.field_key,
                        MobileEvent.id != event.id,
                        MobileEvent.approval_status != "rejected",
                    )
                    .order_by(MobileEvent.received_at.desc(), MobileEvent.id.desc())
                    .limit(1)
                )
                if previous:
                    data[event.field_key] = _field_from_event(previous)
                    restored_event_id = previous.id
                else:
                    data.pop(event.field_key, None)
        else:
            was_rejected = event.approval_status == "rejected"
            event.approval_required = True
            event.approval_status = "approved"
            event.approved_at = decided_at
            event.approved_by_id = operator.id

            if record:
                if is_current:
                    current["approval_required"] = True
                    current["approval_status"] = "approved"
                    current["approved_at"] = decided_at.isoformat()
                    current["approved_by_id"] = operator.id
                elif was_rejected:
                    latest = db.scalar(
                        select(MobileEvent)
                        .where(
                            MobileEvent.permit_number == event.permit_number,
                            MobileEvent.field_key == event.field_key,
                        )
                        .order_by(MobileEvent.received_at.desc(), MobileEvent.id.desc())
                        .limit(1)
                    )
                    if latest and latest.id == event.id:
                        data[event.field_key] = _field_from_event(event)
                        data[event.field_key]["approval_required"] = True
                        data[event.field_key]["approval_status"] = "approved"
                        data[event.field_key]["approved_at"] = decided_at.isoformat()
                        data[event.field_key]["approved_by_id"] = operator.id
                        is_current = True

        if record:
            record.data_json = json.dumps(data, ensure_ascii=False)
            record.updated_at = decided_at
            record.exported_at = None
            record.export_batch_id = None

        db.commit()
        return {
            "status": payload.decision,
            "event_id": event.id,
            "permit_number": event.permit_number,
            "field_key": event.field_key,
            "stage_label": event.stage_label,
            "reason": reason if payload.decision == "rejected" else "",
            "reviewed_at": decided_at.isoformat(),
            "reviewed_by": operator.username,
            "current_value_changed": is_current or restored_event_id is not None,
            "restored_event_id": restored_event_id,
        }

    core.review_transmission = review_transmission

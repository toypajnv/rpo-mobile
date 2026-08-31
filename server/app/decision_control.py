from __future__ import annotations

import json
from typing import Literal

from fastapi import Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import MobileEvent, Operator, PermitRecord
from .services.exporter import record_data


class EventDecisionRequest(BaseModel):
    decision: Literal["approved", "denied"]
    reason: str = Field(default="", max_length=500)


def _decision_summary(core, data: dict) -> dict:
    """Approval summary with permit-wide operator denial support."""
    base = core._decision_control_original_summary(data)
    denied: list[tuple[str, dict]] = []
    for key in core._dashboard_stage_keys():
        if key == "AZ":
            continue
        field = data.get(key) or {}
        if not field or not bool(field.get("approval_required")):
            continue
        if str(field.get("approval_status", "")) == "denied":
            denied.append((key, field))

    if not denied:
        return {
            **base,
            "denied_count": 0,
            "denied_field_key": "",
            "denied_stage": "",
            "denied_reason": "",
            "denied_at": "",
        }

    denied.sort(
        key=lambda item: str(item[1].get("approved_at", "") or item[1].get("decision_at", "")),
        reverse=True,
    )
    key, field = denied[0]
    return {
        **base,
        "status": "denied",
        "label": "Проведение работ запрещено",
        "denied_count": len(denied),
        "denied_field_key": key,
        "denied_stage": core.STAGES.get(key, {}).get("label", key),
        "denied_reason": str(field.get("denied_reason", "")).strip(),
        "denied_at": str(field.get("approved_at", "") or field.get("decision_at", "")).strip(),
    }


def _blocked_message(summary: dict) -> str:
    stage = str(summary.get("denied_stage", "")).strip()
    reason = str(summary.get("denied_reason", "")).strip()
    parts = ["Проведение работ по этому НД запрещено оператором"]
    if stage:
        parts.append(f"этап: {stage}")
    if reason:
        parts.append(f"причина: {reason}")
    return ". ".join(parts) + "."


def install_decision_control(core) -> None:
    """Install additive deny/allow logic without rewriting the preserved core."""
    if getattr(core, "_decision_control_installed", False):
        return
    core._decision_control_installed = True

    core._decision_control_original_summary = core._approval_summary_from_data
    core._approval_summary_from_data = lambda data: _decision_summary(core, data)

    original_validate = core.validate_event

    def validate_event_with_operator_block(db: Session, payload) -> None:
        normalized = payload.permit_number.strip().upper()
        record = db.scalar(select(PermitRecord).where(PermitRecord.permit_number == normalized))
        if record:
            summary = core._approval_summary_from_data(record_data(record))
            if summary.get("status") == "denied":
                raise core.EventValidationError(_blocked_message(summary))
        original_validate(db, payload)

    core.validate_event = validate_event_with_operator_block

    @core.app.post("/api/operator/events/{event_id}/decision")
    def decide_mobile_event(
        event_id: int,
        payload: EventDecisionRequest,
        operator: Operator = Depends(core.current_operator),
        db: Session = Depends(core.get_db),
    ):
        event = db.get(MobileEvent, event_id)
        if not event:
            raise HTTPException(status_code=404, detail="Этап не найден")
        if not event.approval_required or event.field_key == "AZ":
            raise HTTPException(status_code=400, detail="Для этого этапа решение оператора не требуется")

        record = db.scalar(select(PermitRecord).where(PermitRecord.permit_number == event.permit_number))
        if not record:
            raise HTTPException(status_code=404, detail="Наряд-допуск не найден")

        data = record_data(record)
        current = data.get(event.field_key) if isinstance(data.get(event.field_key), dict) else None
        if not current or current.get("client_event_id") != event.client_event_id:
            raise HTTPException(status_code=409, detail="Этот этап уже обновлён с телефона. Примите решение по актуальной записи")

        reason = payload.reason.strip()
        if payload.decision == "denied" and len(reason) < 3:
            raise HTTPException(status_code=400, detail="Укажите причину запрета проведения работ")

        decided_at = core.utcnow()
        event.approval_status = payload.decision
        event.approved_at = decided_at
        event.approved_by_id = operator.id

        current["approval_required"] = True
        current["approval_status"] = payload.decision
        current["approved_at"] = decided_at.isoformat()
        current["approved_by_id"] = operator.id
        current["decision_by"] = operator.username
        if payload.decision == "denied":
            current["denied_reason"] = reason
        else:
            current.pop("denied_reason", None)

        record.data_json = json.dumps(data, ensure_ascii=False)
        record.updated_at = decided_at
        db.commit()

        summary = core._approval_summary_from_data(data)
        return {
            "status": payload.decision,
            "event_id": event.id,
            "permit_number": event.permit_number,
            "field_key": event.field_key,
            "stage_label": event.stage_label,
            "reason": reason if payload.decision == "denied" else "",
            "decided_at": decided_at.isoformat(),
            "decided_by": operator.username,
            "permit_blocked": summary.get("status") == "denied",
            "approval": summary,
        }

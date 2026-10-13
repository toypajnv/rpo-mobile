from datetime import datetime, timezone, timedelta
from sqlalchemy import select
import json
from sqlalchemy.orm import Session
from ..models import MobileEvent, PermitRecord
from ..schemas import EventCreate
from ..stages import STAGES


class EventValidationError(ValueError):
    pass


def _aware_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def validate_event(db: Session, payload: EventCreate) -> None:
    now = datetime.now(timezone.utc)
    event_time = _aware_utc(payload.event_time)
    if event_time > now + timedelta(minutes=5):
        raise EventValidationError("Дата/время события не может быть в будущем")
    if event_time < now - timedelta(days=45):
        raise EventValidationError("Дата события слишком старая. Проверьте дату и время")

    stage = STAGES[payload.field_key]

    # Mandatory stop/resume comments are enforced by current APKs. The server
    # deliberately does not reject a missing comment here: older installed APKs
    # must remain able to synchronize after a server update.
    if stage["kind"] == "text" and len(payload.field_value.strip()) < 2:
        raise EventValidationError("Заполните значение для выбранного этапа")

    after_key = stage.get("after")
    if not after_key:
        return

    # Validate against the current accepted transmission, not an obsolete
    # timestamp from a corrected/superseded row.
    record = db.scalar(
        select(PermitRecord).where(PermitRecord.permit_number == payload.permit_number)
    )
    try:
        active = json.loads(record.data_json or "{}").get(after_key) if record else None
    except (ValueError, TypeError, AttributeError):
        active = None
    if isinstance(active, dict) and active.get("event_time"):
        try:
            prev_time = _aware_utc(datetime.fromisoformat(str(active["event_time"]).replace("Z", "+00:00")))
        except ValueError:
            prev_time = None
        if prev_time is not None and event_time < prev_time:
            raise EventValidationError(
                f"Дата/время этапа не может быть раньше «{active.get('stage_label') or STAGES[after_key]['label']}» "
                f"({prev_time.astimezone().strftime('%d.%m.%Y %H:%M')})"
            )

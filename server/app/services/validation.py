from datetime import datetime, timezone, timedelta
from sqlalchemy import select
from sqlalchemy.orm import Session
from ..models import MobileEvent
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
    if stage.get("comment_required") and len(payload.comment.strip()) < 3:
        if payload.field_key == "BA":
            raise EventValidationError("Для возобновления работ необходимо указать комментарий")
        raise EventValidationError("Для остановки работ необходимо указать причину")

    if stage["kind"] == "text" and len(payload.field_value.strip()) < 2:
        raise EventValidationError("Заполните значение для выбранного этапа")

    after_key = stage.get("after")
    if not after_key:
        return

    previous = db.scalar(
        select(MobileEvent)
        .where(
            MobileEvent.permit_number == payload.permit_number,
            MobileEvent.field_key == after_key,
        )
        .order_by(MobileEvent.event_time.desc())
        .limit(1)
    )
    if previous:
        prev_time = _aware_utc(previous.event_time)
        if event_time < prev_time:
            raise EventValidationError(
                f"Дата/время этапа не может быть раньше «{previous.stage_label}» "
                f"({prev_time.astimezone().strftime('%d.%m.%Y %H:%M')})"
            )

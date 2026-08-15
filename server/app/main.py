from __future__ import annotations
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Annotated
from contextlib import asynccontextmanager
import json

from fastapi import FastAPI, Depends, Form, HTTPException, Request, Query
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware
from sqlalchemy import select, func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .config import settings
from .database import Base, engine, get_db, SessionLocal
from .models import Operator, MobileEvent, ExportBatch, PermitRecord
from .schemas import EventCreate, EventOut
from .security import hash_password, verify_password
from .services.validation import validate_event, EventValidationError
from .services.exporter import build_export, record_data
from .services.mailer import send_export
from .stages import STAGES

BASE_DIR = Path(__file__).resolve().parent
settings.ensure_dirs()


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(engine)
    ensure_admin()
    ensure_permit_records()
    yield


app = FastAPI(title=settings.app_name, version="0.2.0", lifespan=lifespan)
app.add_middleware(SessionMiddleware, secret_key=settings.secret_key, same_site="lax", https_only=True)
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
templates = Jinja2Templates(directory=BASE_DIR / "templates")


def dt_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def ensure_admin() -> None:
    with SessionLocal() as db:
        user = db.scalar(select(Operator).where(Operator.username == settings.admin_username))
        if not user:
            db.add(Operator(username=settings.admin_username, password_hash=hash_password(settings.admin_password)))
            db.commit()


def _safe_data(value: str | None) -> dict:
    try:
        parsed = json.loads(value or "{}")
        return parsed if isinstance(parsed, dict) else {}
    except Exception:
        return {}


def _apply_event_to_record(db: Session, event: MobileEvent) -> PermitRecord:
    record = db.scalar(select(PermitRecord).where(PermitRecord.permit_number == event.permit_number))
    data = _safe_data(record.data_json if record else None)
    data[event.field_key] = {
        "stage_label": event.stage_label,
        "field_value": event.field_value,
        "event_time": event.event_time.isoformat(),
        "comment": event.comment or "",
        "client_event_id": event.client_event_id,
    }
    if record is None:
        record = PermitRecord(
            permit_number=event.permit_number,
            device_id=event.device_id,
            worker_name=event.worker_name,
            data_json=json.dumps(data, ensure_ascii=False),
            first_received_at=event.received_at or utcnow(),
            updated_at=event.received_at or utcnow(),
        )
        db.add(record)
    else:
        record.device_id = event.device_id
        record.worker_name = event.worker_name
        record.data_json = json.dumps(data, ensure_ascii=False)
        record.updated_at = event.received_at or utcnow()
        record.exported_at = None
        record.export_batch_id = None
    return record


def ensure_permit_records() -> None:
    """Backfill the canonical one-row-per-permit table after first deployment."""
    with SessionLocal() as db:
        existing = db.scalar(select(func.count()).select_from(PermitRecord)) or 0
        if existing:
            return
        events = list(db.scalars(select(MobileEvent).order_by(MobileEvent.received_at.asc(), MobileEvent.id.asc())))
        for event in events:
            _apply_event_to_record(db, event)
        db.commit()


def _parse_period(period_from: str, period_to: str) -> tuple[datetime, datetime]:
    try:
        start = datetime.fromisoformat(period_from.replace("Z", "+00:00"))
        end = datetime.fromisoformat(period_to.replace("Z", "+00:00"))
    except ValueError:
        raise HTTPException(status_code=400, detail="Некорректный период")
    if start.tzinfo is None:
        start = start.astimezone()
    if end.tzinfo is None:
        end = end.astimezone()
    start, end = start.astimezone(timezone.utc), end.astimezone(timezone.utc)
    if end < start:
        raise HTTPException(status_code=400, detail="Дата «По» раньше даты «С»")
    return start, end


def _stage_keys() -> list[str]:
    return [key for key, _ in sorted(STAGES.items(), key=lambda item: item[1]["order"])]


def _record_summary(record: PermitRecord) -> tuple[str, str]:
    data = record_data(record)
    values = []
    comments = []
    for key in _stage_keys():
        field = data.get(key) or {}
        value = str(field.get("field_value", "")).strip()
        if value:
            values.append(f"{STAGES[key]['label']}: {value}")
        comment = str(field.get("comment", "")).strip()
        if comment:
            comments.append(f"{STAGES[key]['label']}: {comment}")
    return "\n".join(values) or "Данные ещё не заполнены", "\n".join(comments)


def _preview_record(record: PermitRecord) -> dict:
    data = record_data(record)
    fields = {}
    for key in _stage_keys():
        src = data.get(key) or {}
        fields[key] = {
            "label": STAGES[key]["label"],
            "field_value": str(src.get("field_value", "")),
            "comment": str(src.get("comment", "")),
            "event_time": str(src.get("event_time", "")),
        }
    return {
        "id": record.id,
        "permit_number": record.permit_number,
        "worker_name": record.worker_name,
        "updated_at": record.updated_at.isoformat(),
        "fields": fields,
    }


def current_operator(request: Request, db: Session = Depends(get_db)) -> Operator:
    operator_id = request.session.get("operator_id")
    if not operator_id:
        raise HTTPException(status_code=401, detail="Требуется вход")
    operator = db.get(Operator, operator_id)
    if not operator or not operator.is_active:
        request.session.clear()
        raise HTTPException(status_code=401, detail="Требуется вход")
    return operator


@app.exception_handler(401)
async def auth_error_handler(request: Request, exc: HTTPException):
    if request.url.path.startswith("/api/"):
        return JSONResponse(status_code=401, content={"detail": exc.detail})
    return RedirectResponse("/login", status_code=303)


@app.get("/health")
def health():
    return {"status": "ok", "app": settings.app_name}


@app.get("/", include_in_schema=False)
def root():
    return RedirectResponse("/dashboard", status_code=303)


@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    if request.session.get("operator_id"):
        return RedirectResponse("/dashboard", status_code=303)
    return templates.TemplateResponse(request=request, name="login.html", context={"error": None})


@app.post("/login", response_class=HTMLResponse)
def login(request: Request, username: Annotated[str, Form()], password: Annotated[str, Form()], db: Session = Depends(get_db)):
    operator = db.scalar(select(Operator).where(Operator.username == username.strip()))
    if not operator or not operator.is_active or not verify_password(password, operator.password_hash):
        return templates.TemplateResponse(request=request, name="login.html", context={"error": "Неверный логин или пароль"}, status_code=400)
    request.session["operator_id"] = operator.id
    return RedirectResponse("/dashboard", status_code=303)


@app.post("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/login", status_code=303)


@app.post("/api/mobile/events", response_model=EventOut, status_code=201)
def create_mobile_event(payload: EventCreate, db: Session = Depends(get_db)):
    existing = db.scalar(select(MobileEvent).where(MobileEvent.client_event_id == payload.client_event_id))
    if existing:
        return existing
    try:
        validate_event(db, payload)
    except EventValidationError as e:
        raise HTTPException(status_code=422, detail=str(e))

    event = MobileEvent(
        client_event_id=payload.client_event_id,
        device_id=payload.device_id,
        worker_name=payload.worker_name,
        permit_number=payload.permit_number,
        field_key=payload.field_key,
        stage_label=payload.stage_label,
        event_time=dt_utc(payload.event_time),
        field_value=payload.field_value,
        comment=payload.comment,
    )
    db.add(event)
    try:
        db.flush()
        _apply_event_to_record(db, event)
        db.commit()
    except IntegrityError:
        db.rollback()
        existing = db.scalar(select(MobileEvent).where(MobileEvent.client_event_id == payload.client_event_id))
        if existing:
            return existing
        raise
    db.refresh(event)
    return event


@app.get("/api/mobile/events", response_model=list[EventOut])
def mobile_history(device_id: str = Query(min_length=2), limit: int = Query(30, ge=1, le=100), db: Session = Depends(get_db)):
    events = list(db.scalars(
        select(MobileEvent)
        .where(MobileEvent.device_id == device_id)
        .order_by(MobileEvent.received_at.desc(), MobileEvent.id.desc())
        .limit(500)
    ))
    grouped: dict[str, list[MobileEvent]] = {}
    for event in events:
        grouped.setdefault(event.permit_number, []).append(event)

    result = []
    for permit_events in grouped.values():
        latest = permit_events[0]
        by_key: dict[str, MobileEvent] = {}
        for event in permit_events:
            by_key.setdefault(event.field_key, event)
        values = []
        comments = []
        for key in _stage_keys():
            event = by_key.get(key)
            if not event:
                continue
            values.append(f"{STAGES[key]['label']}: {event.field_value}")
            if (event.comment or "").strip():
                comments.append(f"{STAGES[key]['label']}: {event.comment.strip()}")
        result.append({
            "id": latest.id,
            "worker_name": latest.worker_name,
            "permit_number": latest.permit_number,
            "field_key": "НД",
            "stage_label": f"Наряд-допуск · {len(by_key)} этап(ов)",
            "event_time": latest.event_time,
            "field_value": "\n".join(values),
            "comment": "\n".join(comments),
            "received_at": latest.received_at,
            "exported_at": latest.exported_at,
        })
    result.sort(key=lambda item: item["received_at"], reverse=True)
    return result[:limit]


def dashboard_context(db: Session):
    now = utcnow()
    day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    received_today = db.scalar(select(func.count()).select_from(PermitRecord).where(PermitRecord.updated_at >= day_start)) or 0
    pending = db.scalar(select(func.count()).select_from(PermitRecord).where(PermitRecord.exported_at.is_(None))) or 0
    active_since = now - timedelta(hours=12)
    active_workers = db.scalar(select(func.count(func.distinct(PermitRecord.worker_name))).where(PermitRecord.updated_at >= active_since)) or 0
    last_export = db.scalar(select(ExportBatch).order_by(ExportBatch.created_at.desc()).limit(1))
    records = list(db.scalars(select(PermitRecord).order_by(PermitRecord.updated_at.desc()).limit(100)))
    exports = list(db.scalars(select(ExportBatch).order_by(ExportBatch.created_at.desc()).limit(10)))
    events = []
    for record in records:
        summary, comments = _record_summary(record)
        events.append({
            "id": record.id,
            "updated_at": record.updated_at,
            "worker_name": record.worker_name,
            "permit_number": record.permit_number,
            "summary": summary,
            "comments": comments,
            "exported_at": record.exported_at,
        })
    return dict(received_today=received_today, pending=pending, active_workers=active_workers, last_export=last_export, events=events, exports=exports)


@app.get("/dashboard", response_class=HTMLResponse)
def dashboard(request: Request, operator: Operator = Depends(current_operator), db: Session = Depends(get_db)):
    return templates.TemplateResponse(request=request, name="dashboard.html", context={"operator": operator, **dashboard_context(db)})


@app.get("/api/operator/events")
def operator_events(
    request: Request,
    operator: Operator = Depends(current_operator),
    db: Session = Depends(get_db),
    limit: int = Query(100, ge=1, le=500),
):
    records = list(db.scalars(select(PermitRecord).order_by(PermitRecord.updated_at.desc()).limit(limit)))
    result = []
    for record in records:
        summary, comments = _record_summary(record)
        result.append({
            "id": record.id,
            "updated_at": record.updated_at.isoformat(),
            "worker_name": record.worker_name,
            "permit_number": record.permit_number,
            "summary": summary,
            "comments": comments,
            "exported": bool(record.exported_at),
        })
    return result


@app.get("/api/operator/export-preview")
def export_preview(
    period_from: str,
    period_to: str,
    operator: Operator = Depends(current_operator),
    db: Session = Depends(get_db),
):
    start, end = _parse_period(period_from, period_to)
    records = list(db.scalars(
        select(PermitRecord)
        .where(PermitRecord.updated_at >= start, PermitRecord.updated_at <= end, PermitRecord.exported_at.is_(None))
        .order_by(PermitRecord.updated_at.asc())
    ))
    return {
        "records": [_preview_record(record) for record in records],
        "stage_keys": _stage_keys(),
        "period_from": start.isoformat(),
        "period_to": end.isoformat(),
    }


@app.post("/exports/send")
def send_export_confirmed(
    request: Request,
    period_from: Annotated[str, Form()],
    period_to: Annotated[str, Form()],
    recipient: Annotated[str, Form()],
    edited_json: Annotated[str, Form()],
    operator: Operator = Depends(current_operator),
    db: Session = Depends(get_db),
):
    start, end = _parse_period(period_from, period_to)
    recipient = recipient.strip()
    if "@" not in recipient:
        raise HTTPException(status_code=400, detail="Укажите корректный email")

    recent = db.scalar(
        select(ExportBatch)
        .where(
            ExportBatch.recipient == recipient,
            ExportBatch.period_from == start,
            ExportBatch.period_to == end,
            ExportBatch.created_at >= utcnow() - timedelta(seconds=60),
            ExportBatch.status.in_(["sent", "saved_to_outbox", "created"]),
        )
        .order_by(ExportBatch.created_at.desc())
        .limit(1)
    )
    if recent:
        return RedirectResponse("/dashboard?export=duplicate", status_code=303)

    try:
        edited = json.loads(edited_json)
        if not isinstance(edited, list):
            raise ValueError
    except Exception:
        raise HTTPException(status_code=400, detail="Некорректные данные предпросмотра")

    allowed_records = list(db.scalars(
        select(PermitRecord)
        .where(PermitRecord.updated_at >= start, PermitRecord.updated_at <= end, PermitRecord.exported_at.is_(None))
        .order_by(PermitRecord.updated_at.asc())
    ))
    by_permit = {record.permit_number: record for record in allowed_records}
    selected: list[PermitRecord] = []

    for item in edited:
        permit_number = str(item.get("permit_number", "")).strip().upper()
        record = by_permit.get(permit_number)
        if not record:
            continue
        worker_name = str(item.get("worker_name", "")).strip()
        if len(worker_name) < 3:
            raise HTTPException(status_code=400, detail=f"Для НД {permit_number} не указано ФИО")
        record.worker_name = worker_name[:180]
        current = record_data(record)
        fields = item.get("fields") if isinstance(item.get("fields"), dict) else {}
        for key in _stage_keys():
            incoming = fields.get(key)
            if not isinstance(incoming, dict):
                continue
            value = str(incoming.get("field_value", "")).strip()[:1000]
            comment = str(incoming.get("comment", "")).strip()[:1000]
            existing = current.get(key) if isinstance(current.get(key), dict) else {}
            if value or existing:
                current[key] = {
                    "stage_label": STAGES[key]["label"],
                    "field_value": value,
                    "event_time": existing.get("event_time", ""),
                    "comment": comment,
                    "client_event_id": existing.get("client_event_id", "operator-edit"),
                }
        record.data_json = json.dumps(current, ensure_ascii=False)
        selected.append(record)

    if not selected:
        raise HTTPException(status_code=400, detail="За выбранный период нет невыгруженных нарядов-допусков")

    batch = ExportBatch(
        period_from=start,
        period_to=end,
        recipient=recipient,
        created_by_id=operator.id,
        event_count=len(selected),
    )
    db.add(batch)
    db.flush()
    xlsx_path, json_path = build_export(selected, settings.export_dir, batch.id)

    try:
        send_export(
            recipient,
            f"РПО — выгрузка №{batch.id}",
            (
                f"Выгрузка РПО одним письмом. Нарядов-допусков: {len(selected)}. "
                f"Период: {start.astimezone():%d.%m.%Y %H:%M} — {end.astimezone():%d.%m.%Y %H:%M}.\n\n"
                "Во вложении единая выгрузка по выбранному периоду. Каждому НД соответствует одна строка."
            ),
            [xlsx_path, json_path],
        )
    except Exception as exc:
        batch.status = "error"
        batch.file_name = xlsx_path.name
        db.commit()
        raise HTTPException(status_code=500, detail=f"Файлы сформированы, но отправка не удалась: {exc}")

    sent_at = utcnow()
    batch.status = "sent" if settings.mail_mode.lower() == "smtp" else "saved_to_outbox"
    batch.sent_at = sent_at
    batch.file_name = xlsx_path.name
    permit_numbers = []
    for record in selected:
        record.exported_at = sent_at
        record.export_batch_id = batch.id
        permit_numbers.append(record.permit_number)

    raw_events = list(db.scalars(
        select(MobileEvent).where(
            MobileEvent.permit_number.in_(permit_numbers),
            MobileEvent.received_at <= end,
            MobileEvent.exported_at.is_(None),
        )
    ))
    for event in raw_events:
        event.exported_at = sent_at
        event.export_batch_id = batch.id

    db.commit()
    return RedirectResponse("/dashboard?export=ok", status_code=303)

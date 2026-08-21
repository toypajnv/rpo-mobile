from __future__ import annotations
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Annotated
from contextlib import asynccontextmanager
import json
import hashlib

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
REQUIRED_DASHBOARD_STAGE_KEYS = ("AT", "AU", "AV", "AY", "AZ", "BA", "BE", "BC")
DASHBOARD_STAGE_KEYS = REQUIRED_DASHBOARD_STAGE_KEYS + ("RI",)
LATEST_MOBILE_VERSION = "1.1.5"
MIN_SUPPORTED_MOBILE_VERSION = "1.0.1"
MOBILE_APK_URL = "https://github.com/toypajnv/rpo-mobile/releases/download/v1.1.5-test/rpo-mobile-1.1.5.apk"
DEFAULT_OPERATOR_USERNAME = "Operator"
DEFAULT_OPERATOR_PASSWORD_HASH = "$argon2id$v=19$m=65536,t=3,p=4$hBSN4f5Hetyo+a4aOvCP3A$7bYB1iB2/8/sS0w1AYTNrdAg3QyVP7KdhTOP2PHCNys"
settings.ensure_dirs()


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(engine)
    ensure_admin()
    ensure_default_operator()
    ensure_permit_records()
    yield


app = FastAPI(title=settings.app_name, version="0.4.0", lifespan=lifespan)
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


def ensure_default_operator() -> None:
    """Create the shared Operator account without storing its plain password."""
    with SessionLocal() as db:
        user = db.scalar(select(Operator).where(Operator.username == DEFAULT_OPERATOR_USERNAME))
        if not user:
            db.add(Operator(
                username=DEFAULT_OPERATOR_USERNAME,
                password_hash=DEFAULT_OPERATOR_PASSWORD_HASH,
                is_active=True,
            ))
            db.commit()


def is_admin(operator: Operator | None) -> bool:
    return bool(operator and operator.username == settings.admin_username)


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
            db.flush()
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


def _dashboard_stage_keys() -> list[str]:
    return [key for key in DASHBOARD_STAGE_KEYS if key in STAGES]


def _required_dashboard_stage_keys() -> list[str]:
    return [key for key in REQUIRED_DASHBOARD_STAGE_KEYS if key in STAGES]


def _field_dt(data: dict, key: str) -> datetime | None:
    raw = str((data.get(key) or {}).get("event_time", "")).strip()
    if not raw:
        return None
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except ValueError:
        return None


def _has_stage(data: dict, key: str) -> bool:
    return bool(str((data.get(key) or {}).get("field_value", "")).strip())


def _record_state(record: PermitRecord) -> tuple[str, str]:
    data = record_data(record)
    if _has_stage(data, "BC"):
        return "Завершено", "done"
    stop_at = _field_dt(data, "AZ")
    resume_at = _field_dt(data, "BA")
    if stop_at and (not resume_at or stop_at > resume_at):
        return "Остановлено", "stopped"
    if _has_stage(data, "AY"):
        return ("Продлено", "extended") if _has_stage(data, "BE") else ("В работе", "active")
    if any(_has_stage(data, key) for key in ("AT", "AU", "AV")):
        return "Подготовка", "preparing"
    return "Создано", "new"


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


def _work_view(record: PermitRecord) -> dict:
    data = record_data(record)
    visible_keys = _dashboard_stage_keys()
    required_keys = _required_dashboard_stage_keys()
    filled = sum(1 for key in required_keys if _has_stage(data, key))
    total = len(required_keys) or 1
    summary, comments = _record_summary(record)
    status, status_class = _record_state(record)
    stage_items = []
    for key in visible_keys:
        field = data.get(key) or {}
        value = str(field.get("field_value", "")).strip()
        if not value:
            continue
        stage_items.append({
            "key": key,
            "label": STAGES[key]["label"],
            "value": value,
            "comment": str(field.get("comment", "")).strip(),
        })
    return {
        "id": record.id,
        "updated_at": record.updated_at,
        "worker_name": record.worker_name,
        "permit_number": record.permit_number,
        "summary": summary,
        "comments": comments,
        "exported_at": record.exported_at,
        "status": status,
        "status_class": status_class,
        "progress": round(filled * 100 / total),
        "stage_count": filled,
        "stage_total": total,
        "stage_items": stage_items,
    }


def _preview_record(record: PermitRecord) -> dict:
    data = record_data(record)
    fields = {}
    for key in _dashboard_stage_keys():
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
        "previously_exported": bool(record.exported_at),
        "exported_at": record.exported_at.isoformat() if record.exported_at else "",
        "fields": fields,
    }


def _analytics_context(records: list[PermitRecord], raw_events: list[MobileEvent], now: datetime) -> dict:
    state_counts = {"active": 0, "stopped": 0, "done": 0, "preparing": 0, "extended": 0, "new": 0}
    extended_count = 0
    completion_hours: list[float] = []
    worker_counts: dict[str, int] = {}
    stage_counts = {key: 0 for key in _dashboard_stage_keys()}

    for record in records:
        _, state_class = _record_state(record)
        state_counts[state_class] = state_counts.get(state_class, 0) + 1
        data = record_data(record)
        if _has_stage(data, "BE"):
            extended_count += 1
        start_dt = _field_dt(data, "AY")
        finish_dt = _field_dt(data, "BC")
        if start_dt and finish_dt and finish_dt >= start_dt:
            completion_hours.append((finish_dt - start_dt).total_seconds() / 3600)
        worker_counts[record.worker_name] = worker_counts.get(record.worker_name, 0) + 1
        for key in stage_counts:
            if _has_stage(data, key):
                stage_counts[key] += 1

    start_day = (now - timedelta(days=6)).date()
    daily = {start_day + timedelta(days=i): 0 for i in range(7)}
    for event in raw_events:
        received = event.received_at
        if received.tzinfo is None:
            received = received.replace(tzinfo=timezone.utc)
        day = received.astimezone(timezone.utc).date()
        if day in daily:
            daily[day] += 1
    max_daily = max(daily.values(), default=0) or 1
    activity_days = [
        {"label": day.strftime("%d.%m"), "count": count, "pct": round(count * 100 / max_daily)}
        for day, count in daily.items()
    ]

    total = len(records)
    stage_progress = [
        {
            "key": key,
            "label": STAGES[key]["label"],
            "count": count,
            "pct": round(count * 100 / total) if total else 0,
        }
        for key, count in stage_counts.items()
        if count
    ]
    top_workers = [
        {"name": name, "count": count}
        for name, count in sorted(worker_counts.items(), key=lambda item: (-item[1], item[0].lower()))[:5]
    ]
    avg_completion_hours = sum(completion_hours) / len(completion_hours) if completion_hours else None
    if avg_completion_hours is None:
        avg_completion_label = "—"
    elif avg_completion_hours < (1 / 60):
        avg_completion_label = "< 1 мин"
    elif avg_completion_hours < 1:
        avg_completion_label = f"{max(1, round(avg_completion_hours * 60))} мин"
    else:
        avg_completion_label = f"{avg_completion_hours:.1f} ч"

    return {
        "total": total,
        "active": state_counts.get("active", 0) + state_counts.get("extended", 0),
        "stopped": state_counts.get("stopped", 0),
        "completed": state_counts.get("done", 0),
        "preparing": state_counts.get("preparing", 0),
        "extended": extended_count,
        "avg_completion_hours": round(avg_completion_hours, 1) if avg_completion_hours is not None else None,
        "avg_completion_label": avg_completion_label,
        "activity_days": activity_days,
        "stage_progress": stage_progress,
        "top_workers": top_workers,
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


def _effective_client_event_id(payload: EventCreate) -> str:
    if payload.client_event_id:
        return payload.client_event_id
    raw = "|".join([
        payload.device_id,
        payload.worker_name,
        payload.permit_number,
        payload.field_key,
        payload.event_time.isoformat(),
        payload.field_value,
        payload.comment,
    ])
    return "legacy-" + hashlib.sha256(raw.encode("utf-8")).hexdigest()[:48]


@app.post("/api/mobile/events", response_model=EventOut, status_code=201)
def create_mobile_event(payload: EventCreate, db: Session = Depends(get_db)):
    client_event_id = _effective_client_event_id(payload)
    existing = db.scalar(select(MobileEvent).where(MobileEvent.client_event_id == client_event_id))
    if existing:
        return existing
    try:
        validate_event(db, payload)
    except EventValidationError as e:
        raise HTTPException(status_code=422, detail=str(e))

    event = MobileEvent(
        client_event_id=client_event_id,
        device_id=payload.device_id,
        worker_name=payload.worker_name,
        permit_number=payload.permit_number,
        field_key=payload.field_key,
        stage_label=payload.stage_label.strip() or STAGES[payload.field_key]["label"],
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


def _version_tuple(value: str) -> tuple[int, int, int]:
    parts = []
    for raw in (value or "").split(".")[:3]:
        digits = "".join(ch for ch in raw if ch.isdigit())
        parts.append(int(digits or 0))
    while len(parts) < 3:
        parts.append(0)
    return tuple(parts[:3])


@app.get("/api/mobile/config")
def mobile_config(app_version: str = Query(default="", max_length=32)):
    update_available = bool(app_version) and _version_tuple(app_version) < _version_tuple(LATEST_MOBILE_VERSION)
    message = "Связь с сервером установлена. Система РПО работает штатно."
    if update_available:
        message += f" Доступна версия приложения {LATEST_MOBILE_VERSION}."
    return {
        "status": "ok",
        "server_version": app.version,
        "latest_app_version": LATEST_MOBILE_VERSION,
        "minimum_supported_version": MIN_SUPPORTED_MOBILE_VERSION,
        "update_available": update_available,
        "update_required": False,
        "maintenance": False,
        "message": message,
        "apk_url": MOBILE_APK_URL,
        "checked_at": utcnow().isoformat(),
    }


@app.get("/api/mobile/permit")
def mobile_permit_lookup(
    permit_number: str = Query(min_length=3, max_length=80),
    db: Session = Depends(get_db),
):
    normalized = permit_number.strip().upper()
    record = db.scalar(select(PermitRecord).where(PermitRecord.permit_number == normalized))
    if not record:
        raise HTTPException(status_code=404, detail="Наряд-допуск не найден")
    data = record_data(record)
    fields = {
        key: {
            "field_value": str((data.get(key) or {}).get("field_value", "")),
            "event_time": str((data.get(key) or {}).get("event_time", "")),
            "comment": str((data.get(key) or {}).get("comment", "")),
        }
        for key in _dashboard_stage_keys()
        if data.get(key)
    }
    return {
        "permit_number": record.permit_number,
        "worker_name": record.worker_name,
        "updated_at": record.updated_at.isoformat(),
        "fields": fields,
    }


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

    all_records = list(db.scalars(select(PermitRecord).order_by(PermitRecord.updated_at.desc())))
    works = [_work_view(record) for record in all_records[:200]]
    exports = list(db.scalars(select(ExportBatch).order_by(ExportBatch.created_at.desc()).limit(30)))
    transmissions_raw = list(db.scalars(select(MobileEvent).order_by(MobileEvent.received_at.desc(), MobileEvent.id.desc()).limit(300)))
    transmissions = [
        {
            "id": event.id,
            "received_at": event.received_at,
            "worker_name": event.worker_name,
            "permit_number": event.permit_number,
            "field_key": event.field_key,
            "stage_label": event.stage_label,
            "field_value": event.field_value,
            "comment": event.comment,
            "exported_at": event.exported_at,
        }
        for event in transmissions_raw
    ]
    analytics_events = list(db.scalars(
        select(MobileEvent)
        .where(MobileEvent.received_at >= now - timedelta(days=7))
        .order_by(MobileEvent.received_at.asc())
    ))
    analytics = _analytics_context(all_records, analytics_events, now)
    settings_view = {
        "mail_provider": "Resend API" if settings.mail_mode.lower() == "resend" else ("SMTP" if settings.mail_mode.lower() == "smtp" else "Локальный outbox"),
        "mail_from": settings.resend_from if settings.mail_mode.lower() == "resend" else settings.smtp_from,
        "mail_ready": bool(settings.resend_api_key) if settings.mail_mode.lower() == "resend" else bool(settings.smtp_host) if settings.mail_mode.lower() == "smtp" else True,
        "database": "PostgreSQL" if settings.database_url.startswith("postgresql") else "SQLite",
        "app_version": app.version,
        "mobile_version": LATEST_MOBILE_VERSION,
    }
    users = list(db.scalars(select(Operator).order_by(Operator.username.asc())))
    return dict(
        received_today=received_today,
        pending=pending,
        active_workers=active_workers,
        last_export=last_export,
        works=works,
        transmissions=transmissions,
        exports=exports,
        analytics=analytics,
        settings_view=settings_view,
        users=users,
    )


@app.get("/dashboard", response_class=HTMLResponse)
def dashboard(request: Request, operator: Operator = Depends(current_operator), db: Session = Depends(get_db)):
    return templates.TemplateResponse(
        request=request,
        name="dashboard.html",
        context={"operator": operator, "is_admin": is_admin(operator), **dashboard_context(db)},
    )


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
        item = _work_view(record)
        result.append({
            "id": item["id"],
            "updated_at": item["updated_at"].isoformat(),
            "worker_name": item["worker_name"],
            "permit_number": item["permit_number"],
            "summary": item["summary"],
            "comments": item["comments"],
            "exported": bool(item["exported_at"]),
            "status": item["status"],
            "status_class": item["status_class"],
            "progress": item["progress"],
            "stage_count": item["stage_count"],
            "stage_total": item["stage_total"],
            "stage_items": item["stage_items"],
            "can_delete": is_admin(operator),
        })
    return result


@app.get("/api/operator/transmissions")
def operator_transmissions(
    operator: Operator = Depends(current_operator),
    db: Session = Depends(get_db),
    limit: int = Query(200, ge=1, le=500),
):
    events = list(db.scalars(
        select(MobileEvent)
        .order_by(MobileEvent.received_at.desc(), MobileEvent.id.desc())
        .limit(limit)
    ))
    return [
        {
            "id": event.id,
            "received_at": event.received_at.isoformat(),
            "worker_name": event.worker_name,
            "permit_number": event.permit_number,
            "field_key": event.field_key,
            "stage_label": event.stage_label,
            "field_value": event.field_value,
            "comment": event.comment or "",
            "exported": bool(event.exported_at),
        }
        for event in events
    ]


@app.delete("/api/operator/permits/{record_id}")
def delete_permit_record(
    record_id: int,
    operator: Operator = Depends(current_operator),
    db: Session = Depends(get_db),
):
    if not is_admin(operator):
        raise HTTPException(status_code=403, detail="Удаление доступно только администратору")
    record = db.get(PermitRecord, record_id)
    if not record:
        raise HTTPException(status_code=404, detail="Наряд-допуск не найден")
    permit_number = record.permit_number
    raw_events = list(db.scalars(select(MobileEvent).where(MobileEvent.permit_number == permit_number)))
    for event in raw_events:
        db.delete(event)
    db.delete(record)
    db.commit()
    return {"status": "deleted", "permit_number": permit_number, "events_deleted": len(raw_events)}


@app.post("/users/{operator_id}/password")
def reset_operator_password(
    operator_id: int,
    password: Annotated[str, Form()],
    operator: Operator = Depends(current_operator),
    db: Session = Depends(get_db),
):
    if not is_admin(operator):
        raise HTTPException(status_code=403, detail="Управление пользователями доступно только администратору")
    target = db.get(Operator, operator_id)
    if not target:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    if len(password) < 10:
        raise HTTPException(status_code=400, detail="Пароль должен содержать не менее 10 символов")
    target.password_hash = hash_password(password)
    target.is_active = True
    db.commit()
    return RedirectResponse("/dashboard?user=password-updated#users", status_code=303)


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
        .where(PermitRecord.updated_at >= start, PermitRecord.updated_at <= end)
        .order_by(PermitRecord.updated_at.asc())
    ))
    return {
        "records": [_preview_record(record) for record in records],
        "stage_keys": _dashboard_stage_keys(),
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

    try:
        edited = json.loads(edited_json)
        if not isinstance(edited, list):
            raise ValueError
    except Exception:
        raise HTTPException(status_code=400, detail="Некорректные данные предпросмотра")

    allowed_records = list(db.scalars(
        select(PermitRecord)
        .where(PermitRecord.updated_at >= start, PermitRecord.updated_at <= end)
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
        for key in _dashboard_stage_keys():
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
        raise HTTPException(status_code=400, detail="За выбранный период нет нарядов-допусков")

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
        delivery_result = send_export(
            recipient,
            f"РПО — выгрузка №{batch.id}",
            (
                f"Выгрузка РПО одним письмом. Нарядов-допусков: {len(selected)}. "
                f"Период: {start.astimezone():%d.%m.%Y %H:%M} — {end.astimezone():%d.%m.%Y %H:%M}.\n\n"
                "Во вложении единая выгрузка по выбранному периоду. Каждому НД соответствует одна строка."
            ),
            [xlsx_path, json_path],
            idempotency_key=f"rpo-export-{batch.id}",
        )
    except Exception as exc:
        batch.status = "error"
        batch.file_name = xlsx_path.name
        db.commit()
        raise HTTPException(status_code=500, detail=f"Файлы сформированы, но отправка не удалась: {exc}")

    sent_at = utcnow()
    batch.status = "saved_to_outbox" if delivery_result.startswith("file:") else "sent"
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
    return RedirectResponse("/dashboard?export=ok#exports", status_code=303)
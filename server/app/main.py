from __future__ import annotations
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Annotated
from contextlib import asynccontextmanager
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
from .models import Operator, MobileEvent, ExportBatch
from .schemas import EventCreate, EventOut
from .security import hash_password, verify_password
from .services.validation import validate_event, EventValidationError
from .services.exporter import build_export
from .services.mailer import send_export

BASE_DIR = Path(__file__).resolve().parent
settings.ensure_dirs()

@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(engine)
    ensure_admin()
    yield

app = FastAPI(title=settings.app_name, version="0.1.0", lifespan=lifespan)
app.add_middleware(SessionMiddleware, secret_key=settings.secret_key, same_site="lax", https_only=False)
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
templates = Jinja2Templates(directory=BASE_DIR / "templates")


def dt_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def ensure_admin() -> None:
    with SessionLocal() as db:
        user = db.scalar(select(Operator).where(Operator.username == settings.admin_username))
        if not user:
            db.add(Operator(username=settings.admin_username, password_hash=hash_password(settings.admin_password)))
            db.commit()


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
    return list(db.scalars(
        select(MobileEvent).where(MobileEvent.device_id == device_id).order_by(MobileEvent.received_at.desc()).limit(limit)
    ))


def dashboard_context(db: Session):
    now = datetime.now(timezone.utc)
    day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    received_today = db.scalar(select(func.count()).select_from(MobileEvent).where(MobileEvent.received_at >= day_start)) or 0
    pending = db.scalar(select(func.count()).select_from(MobileEvent).where(MobileEvent.exported_at.is_(None))) or 0
    active_since = now - timedelta(hours=12)
    active_workers = db.scalar(select(func.count(func.distinct(MobileEvent.worker_name))).where(MobileEvent.received_at >= active_since)) or 0
    last_export = db.scalar(select(ExportBatch).order_by(ExportBatch.created_at.desc()).limit(1))
    events = list(db.scalars(select(MobileEvent).order_by(MobileEvent.received_at.desc()).limit(100)))
    exports = list(db.scalars(select(ExportBatch).order_by(ExportBatch.created_at.desc()).limit(10)))
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
    events = list(db.scalars(select(MobileEvent).order_by(MobileEvent.received_at.desc()).limit(limit)))
    return [{
        "id": e.id, "received_at": e.received_at.isoformat(), "worker_name": e.worker_name,
        "permit_number": e.permit_number, "stage_label": e.stage_label, "field_key": e.field_key,
        "field_value": e.field_value, "comment": e.comment, "event_time": e.event_time.isoformat(),
        "exported": bool(e.exported_at),
    } for e in events]


@app.post("/exports")
def create_export(
    request: Request,
    period_from: Annotated[str, Form()],
    period_to: Annotated[str, Form()],
    recipient: Annotated[str, Form()],
    operator: Operator = Depends(current_operator),
    db: Session = Depends(get_db),
):
    try:
        start = datetime.fromisoformat(period_from)
        end = datetime.fromisoformat(period_to)
    except ValueError:
        raise HTTPException(status_code=400, detail="Некорректный период")
    if start.tzinfo is None:
        start = start.astimezone()
    if end.tzinfo is None:
        end = end.astimezone()
    start, end = start.astimezone(timezone.utc), end.astimezone(timezone.utc)
    if end < start:
        raise HTTPException(status_code=400, detail="Дата «По» раньше даты «С»")
    if "@" not in recipient:
        raise HTTPException(status_code=400, detail="Укажите корректный email")

    events = list(db.scalars(
        select(MobileEvent)
        .where(MobileEvent.received_at >= start, MobileEvent.received_at <= end, MobileEvent.exported_at.is_(None))
        .order_by(MobileEvent.received_at.asc())
    ))
    if not events:
        raise HTTPException(status_code=400, detail="За выбранный период нет невыгруженных данных")

    batch = ExportBatch(period_from=start, period_to=end, recipient=recipient.strip(), created_by_id=operator.id, event_count=len(events))
    db.add(batch)
    db.commit(); db.refresh(batch)
    xlsx_path, json_path = build_export(events, settings.export_dir, batch.id)
    try:
        send_export(
            recipient.strip(),
            f"РПО — выгрузка №{batch.id}",
            f"Выгрузка данных РПО. Событий: {len(events)}. Период: {start.astimezone():%d.%m.%Y %H:%M} — {end.astimezone():%d.%m.%Y %H:%M}.\n\nФайл оператор вручную переносит в локальную систему.",
            [xlsx_path, json_path],
        )
    except Exception as exc:
        batch.status = "error"
        batch.file_name = xlsx_path.name
        db.commit()
        raise HTTPException(status_code=500, detail=f"Файлы сформированы, но отправка не удалась: {exc}")

    sent_at = datetime.now(timezone.utc)
    batch.status = "sent" if settings.mail_mode == "smtp" else "saved_to_outbox"
    batch.sent_at = sent_at
    batch.file_name = xlsx_path.name
    for e in events:
        e.exported_at = sent_at
        e.export_batch_id = batch.id
    db.commit()
    return RedirectResponse("/dashboard?export=ok", status_code=303)

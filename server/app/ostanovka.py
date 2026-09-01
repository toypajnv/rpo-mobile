from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from .database import get_db
from .stop_registry import StopRegistryImport, StopRegistryRecord, lookup_pass, normalize_pass_number
from .ukz_registry import UkzBlockImport, find_ukz_block

BASE_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=BASE_DIR / "templates")
router = APIRouter()


class PassCheckRequest(BaseModel):
    pass_number: str = Field(min_length=2, max_length=40)


def _normalize_user_pass(value: str) -> str:
    normalized = normalize_pass_number(value)
    if not normalized:
        raise ValueError("Введите корректный номер пропуска")
    if normalized[-1:].isalpha():
        if not normalized.endswith("C"):
            raise ValueError("Номер пропуска должен заканчиваться на С")
        return normalized
    return normalized + "C"


def _pass_candidates(canonical_pass: str) -> list[str]:
    candidates = [canonical_pass]
    # Historical rows in the first registry may contain numeric pass numbers
    # without the C/С suffix. Keep them searchable while normalizing all new
    # worker input to the required *С format.
    if canonical_pass.endswith("C") and canonical_pass[:-1]:
        candidates.append(canonical_pass[:-1])
    return candidates


def _latest_record(db: Session, pass_number: str) -> StopRegistryRecord | None:
    return db.scalar(
        select(StopRegistryRecord)
        .where(StopRegistryRecord.pass_number == pass_number)
        .order_by(StopRegistryRecord.record_date.desc(), StopRegistryRecord.source_row.desc())
        .limit(1)
    )


def _resolve_registry_record(db: Session, canonical_pass: str) -> tuple[str, StopRegistryRecord | None]:
    for candidate in _pass_candidates(canonical_pass):
        record = _latest_record(db, candidate)
        if record is not None:
            return candidate, record
    return canonical_pass, None


def _apply_access_policy(result: dict, record: StopRegistryRecord | None, *, reason_override: str | None = None) -> dict:
    """Apply the facility access rule from the main stop registry.

    Only an explicit value containing "Запрещен" blocks access. An empty field,
    "Разрешен", or any other non-denial value is treated as allowed.
    """
    if record is None:
        return {
            **result,
            "status": "allowed",
            "title": "Доступ разрешен",
            "message": "Ограничений на доступ по реестру нет.",
            "reason": "",
            "requirements": [],
            "blocks": [],
        }

    access_text = (record.access_status or "").strip().upper().replace("Ё", "Е")
    if "ЗАПРЕЩ" not in access_text:
        return {
            "pass_number": result["pass_number"],
            "status": "allowed",
            "title": "Доступ разрешен",
            "message": "Ограничений на доступ по реестру нет.",
            "reason": "",
            "requirements": [],
            "blocks": [],
        }

    # stop_reason is imported from the workbook column
    # "Причина приостановки работ по Классификатору". This is the only
    # description that may be exposed in the public spoiler.
    reason = (reason_override if reason_override is not None else (record.stop_reason or "")).strip()
    registry_block = {
        "type": "registry",
        "title": "Блокировка по реестру остановок",
        "message": "Доступ ограничен по реестру остановок.",
        "description": reason,
    }
    return {
        **result,
        "status": "denied",
        "title": "Доступ запрещен",
        "message": "Блокировка по реестру остановок.",
        "reason": reason,
        "blocks": [registry_block],
    }


def _resolve_denial_reason(db: Session, record: StopRegistryRecord | None) -> str:
    if record is None:
        return ""
    current = (record.stop_reason or "").strip()
    if current:
        return current

    fallback = db.scalar(
        select(StopRegistryRecord.stop_reason)
        .where(
            StopRegistryRecord.pass_number == record.pass_number,
            StopRegistryRecord.stop_reason != "",
        )
        .order_by(StopRegistryRecord.record_date.desc(), StopRegistryRecord.source_row.desc())
        .limit(1)
    )
    return (fallback or "").strip()


def _resolve_fio(db: Session, record: StopRegistryRecord | None) -> str:
    if record is None:
        return ""
    current = (record.fio or "").strip()
    if current:
        return current
    fallback = db.scalar(
        select(StopRegistryRecord.fio)
        .where(
            StopRegistryRecord.pass_number == record.pass_number,
            StopRegistryRecord.fio != "",
        )
        .order_by(StopRegistryRecord.record_date.desc(), StopRegistryRecord.source_row.desc())
        .limit(1)
    )
    return (fallback or "").strip()


def _apply_ukz_policy(result: dict, ukz_match: dict | None) -> dict:
    if not ukz_match:
        return result

    blocks = list(result.get("blocks") or [])
    if ukz_match.get("kind") == "video":
        block = {
            "type": "video",
            "title": "Блокировка по видеоаналитике",
            "message": "",
            # Public violation details are intentionally limited to the main
            # stop registry. UKZ/video descriptions are not returned to UI.
            "description": "",
        }
    else:
        # Keep the corporate-protection reference only once in the card.
        block = {
            "type": "corporate",
            "title": "Пропуск заблокирован",
            "message": "Обратитесь в Блок корпоративной защиты",
            "description": "",
        }
    blocks.append(block)

    # The block card itself carries the single restriction message. Do not
    # repeat it above the card. For combined restrictions keep one summary.
    message = "" if len(blocks) == 1 else "Обнаружено несколько ограничений доступа."
    return {
        **result,
        "status": "denied",
        "title": "Доступ запрещен",
        "message": message,
        "blocks": blocks,
    }


@router.get("/ostanovka/", response_class=HTMLResponse)
def ostanovka_page(request: Request):
    response = templates.TemplateResponse(request=request, name="ostanovka.html", context={})
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-Robots-Tag"] = "noindex, nofollow"
    return response


@router.post("/api/ostanovka/check")
def ostanovka_check(payload: PassCheckRequest, db: Session = Depends(get_db)):
    registry_ready = db.scalar(select(StopRegistryImport.id).limit(1))
    if not registry_ready:
        raise HTTPException(status_code=503, detail="Реестр остановок еще не загружен. Проверка временно недоступна.")

    try:
        canonical_pass = _normalize_user_pass(payload.pass_number)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    matched_pass, record = _resolve_registry_record(db, canonical_pass)
    try:
        result = lookup_pass(db, matched_pass)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    result["pass_number"] = canonical_pass

    reason = _resolve_denial_reason(db, record)
    result = _apply_access_policy(result, record, reason_override=reason)

    # The UKZ file has no pass number. Link it through the person's FIO from the
    # first registry. Full names and forms like "Иванов И.И." are both supported.
    if db.scalar(select(UkzBlockImport.id).limit(1)):
        fio = _resolve_fio(db, record)
        if fio:
            result = _apply_ukz_policy(result, find_ukz_block(db, fio))

    response = JSONResponse(result)
    response.headers["Cache-Control"] = "no-store"
    return response

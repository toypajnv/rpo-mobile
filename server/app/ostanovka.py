from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from .database import get_db
from .stop_registry import StopRegistryImport, StopRegistryRecord, lookup_pass

BASE_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=BASE_DIR / "templates")
router = APIRouter()


class PassCheckRequest(BaseModel):
    pass_number: str = Field(min_length=2, max_length=40)


def _apply_access_policy(result: dict, record: StopRegistryRecord | None) -> dict:
    """Apply the business rule for access to the facility.

    Only an explicit value containing "Запрещен" blocks access. An empty field,
    "Разрешен", or any other non-denial value is treated as allowed. For an
    explicit denial the stop reason from the registry is returned to the worker.
    """
    if record is None:
        return result

    access_text = (record.access_status or "").strip().upper().replace("Ё", "Е")
    if "ЗАПРЕЩ" not in access_text:
        return {
            "pass_number": result["pass_number"],
            "status": "allowed",
            "title": "Доступ разрешен",
            "message": "Ограничений на доступ по реестру нет.",
            "reason": "",
            "requirements": [],
        }

    reason = (record.stop_reason or "").strip()
    return {
        **result,
        "status": "denied",
        "title": "Доступ запрещен",
        "message": f"Причина: {reason}" if reason else "Причина запрета в реестре не указана.",
        "reason": reason,
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
        result = lookup_pass(db, payload.pass_number)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    record = db.scalar(
        select(StopRegistryRecord)
        .where(StopRegistryRecord.pass_number == result["pass_number"])
        .order_by(StopRegistryRecord.record_date.desc(), StopRegistryRecord.source_row.desc())
        .limit(1)
    )
    result = _apply_access_policy(result, record)

    response = JSONResponse(result)
    response.headers["Cache-Control"] = "no-store"
    return response

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from .database import get_db
from .stop_registry import lookup_pass

BASE_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=BASE_DIR / "templates")
router = APIRouter()


class PassCheckRequest(BaseModel):
    pass_number: str = Field(min_length=2, max_length=40)


@router.get("/ostanovka/", response_class=HTMLResponse)
def ostanovka_page(request: Request):
    response = templates.TemplateResponse(request=request, name="ostanovka.html", context={})
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-Robots-Tag"] = "noindex, nofollow"
    return response


@router.post("/api/ostanovka/check")
def ostanovka_check(payload: PassCheckRequest, db: Session = Depends(get_db)):
    try:
        result = lookup_pass(db, payload.pass_number)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    response = JSONResponse(result)
    response.headers["Cache-Control"] = "no-store"
    return response

"""Separate, password-protected vacancies login. Does not grant RPO access."""
from __future__ import annotations

import hmac
import os
import time
from typing import Annotated
from fastapi import APIRouter, Form, Request
from fastapi.responses import RedirectResponse, HTMLResponse
from .security import verify_password

router = APIRouter()
# Argon2id verifier for the user-requested initial account; plaintext is never in Git.
# Replace with VACANCY_ADMIN_PASSWORD_HASH in the VPS environment to rotate.
DEFAULT_HASH = "$argon2id$v=19$m=65536,t=3,p=2$PHzNhBhkRwGqf3zcVPwRKg$TEvXaJFAtfrji6qKFfclzav/fyMGn1YbZgV6ecC6Oos"
FAILED_ATTEMPTS: dict[str, tuple[int, float]] = {}

def vacancy_logged_in(request: Request) -> bool:
    return (request.session.get("vacancies_auth") == "admin"
            and isinstance(request.session.get("vacancies_expires"), (float, int))
            and request.session["vacancies_expires"] > time.time())

@router.get("/vacancies/login", response_class=HTMLResponse, include_in_schema=False)
def vacancy_login_page(request: Request):
    if vacancy_logged_in(request):
        return RedirectResponse("/vacancies", status_code=303)
    from .main_core import templates
    return templates.TemplateResponse(
        request=request, name="vacancy_login.html", context={"error": ""},
        headers={"Cache-Control": "private, no-store"},
    )

@router.post("/vacancies/login", response_class=HTMLResponse, include_in_schema=False)
def vacancy_login(request: Request, username: Annotated[str, Form()], password: Annotated[str, Form()]):
    from .main_core import templates
    ip = (request.client.host if request.client else "unknown")[:64]
    count, locked_until = FAILED_ATTEMPTS.get(ip, (0, 0))
    if locked_until > time.time():
        return templates.TemplateResponse(
            request=request, name="vacancy_login.html",
            context={"error": "Много попыток входа. Повторите через 15 минут."},
            status_code=429, headers={"Cache-Control": "private, no-store"},
        )
    user = os.getenv("VACANCY_ADMIN_USERNAME", "admin")
    password_hash = os.getenv("VACANCY_ADMIN_PASSWORD_HASH", DEFAULT_HASH)
    valid = hmac.compare_digest(username.strip(), user) and verify_password(password, password_hash)
    if not valid:
        attempts = count + 1
        FAILED_ATTEMPTS[ip] = (attempts, time.time() + 900 if attempts >= 5 else 0)
        return templates.TemplateResponse(
            request=request, name="vacancy_login.html",
            context={"error": "Неверный логин или пароль."},
            status_code=400, headers={"Cache-Control": "private, no-store"},
        )
    FAILED_ATTEMPTS.pop(ip, None)
    request.session["vacancies_auth"] = "admin"
    request.session["vacancies_expires"] = time.time() + 8 * 3600
    return RedirectResponse("/vacancies", status_code=303)

@router.post("/vacancies/logout", include_in_schema=False)
def vacancy_logout(request: Request):
    request.session.pop("vacancies_auth", None)
    request.session.pop("vacancies_expires", None)
    return RedirectResponse("/vacancies/login", status_code=303)

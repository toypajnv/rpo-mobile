from __future__ import annotations

import inspect
from typing import Annotated

from fastapi import Depends, Form, HTTPException
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import Operator


MANAGER_ROLE = "manager"
OPERATOR_ROLE = "operator"
ALLOWED_PANEL_ROLES = {OPERATOR_ROLE, MANAGER_ROLE}


def is_manager(operator: Operator | None) -> bool:
    return bool(operator and (getattr(operator, "role", OPERATOR_ROLE) or OPERATOR_ROLE) == MANAGER_ROLE)


def _assert_manager_read_only(operator: Operator | None) -> None:
    if is_manager(operator):
        raise HTTPException(
            status_code=403,
            detail="Роль «Руководитель» работает только в режиме просмотра. Согласование, запрет, изменение, удаление и отправка выгрузок недоступны.",
        )


def _is_protected_mutation_route(path: str, methods: set[str]) -> bool:
    if not methods.intersection({"POST", "PUT", "PATCH", "DELETE"}):
        return False
    protected_prefixes = ("/api/operator/", "/exports/", "/users/", "/settings/")
    protected_exact = {"/api/operator", "/exports", "/users", "/settings"}
    return path in protected_exact or path.startswith(protected_prefixes)


def _guard_route_for_manager(route) -> None:
    dependant = getattr(route, "dependant", None)
    original = getattr(dependant, "call", None)
    if not callable(original) or getattr(route, "_manager_read_only_guard", False):
        return

    if inspect.iscoroutinefunction(original):
        async def guarded(**kwargs):
            _assert_manager_read_only(kwargs.get("operator"))
            return await original(**kwargs)
    else:
        def guarded(**kwargs):
            _assert_manager_read_only(kwargs.get("operator"))
            return original(**kwargs)

    route._manager_read_only_guard = True
    route.endpoint = guarded
    dependant.call = guarded


def install_manager_access(core) -> None:
    """Install the read-only management role without rewriting stable core routes."""
    if getattr(core, "_manager_access_installed", False):
        return
    core._manager_access_installed = True

    @core.app.post("/users/create")
    def create_operator_user(
        username: Annotated[str, Form()],
        password: Annotated[str, Form()],
        role: Annotated[str, Form()] = MANAGER_ROLE,
        operator: Operator = Depends(core.current_operator),
        db: Session = Depends(core.get_db),
    ):
        if not core.is_admin(operator):
            raise HTTPException(status_code=403, detail="Управление пользователями доступно только администратору")

        username = username.strip()
        role = role.strip().lower()
        if len(username) < 3 or len(username) > 80:
            raise HTTPException(status_code=400, detail="Логин должен содержать от 3 до 80 символов")
        if len(password) < 10:
            raise HTTPException(status_code=400, detail="Пароль должен содержать не менее 10 символов")
        if role not in ALLOWED_PANEL_ROLES:
            raise HTTPException(status_code=400, detail="Неизвестная роль пользователя")

        existing = db.scalar(select(Operator).where(Operator.username == username))
        if existing:
            return RedirectResponse("/dashboard?user=exists#users", status_code=303)

        user = Operator(
            username=username,
            password_hash=core.hash_password(password),
            role=role,
            is_active=True,
        )
        db.add(user)
        db.commit()
        return RedirectResponse(f"/dashboard?user=created&role={role}#users", status_code=303)

    core.create_operator_user = create_operator_user
    core.is_manager = is_manager

    for route in list(core.app.routes):
        path = str(getattr(route, "path", ""))
        methods = set(getattr(route, "methods", set()) or set())
        if _is_protected_mutation_route(path, methods):
            _guard_route_for_manager(route)

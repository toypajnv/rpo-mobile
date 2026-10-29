"""Read-only vacancy monitoring, deliberately isolated from RPO operational data.

Job offers are retrieved from HeadHunter's official API, not scraped from
login-protected corporate websites. A separate worker performs hourly scans.
"""
from __future__ import annotations

import json
import hmac
import secrets
from types import SimpleNamespace
from typing import Annotated
import logging
import os
import re
import time
from datetime import datetime, timedelta, timezone
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request as UrlRequest, urlopen

from fastapi import APIRouter, Depends, Query, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import Boolean, DateTime, Integer, String, Text, UniqueConstraint, func, select
from sqlalchemy.orm import Mapped, Session, mapped_column

from .database import Base, SessionLocal, engine, get_db
from .security import verify_password
from .vacancy_specialties import SPECIALTIES, classify_specialty, specialty_condition
from .vacancy_hh_oauth import get_access_token

log = logging.getLogger("vacancies")
router = APIRouter()
DEFAULT_VACANCY_HASH = "$argon2id$v=19$m=65536,t=3,p=2$PHzNhBhkRwGqf3zcVPwRKg$TEvXaJFAtfrji6qKFfclzav/fyMGn1YbZgV6ecC6Oos"
# A salted password verifier, not plaintext; override via VACANCY_ADMIN_PASSWORD_HASH.
VACANCY_SESSION_HOURS = 8
AUTH_ATTEMPTS: dict[str, tuple[int, float]] = {}
SOURCES_FILTER = ("hh.ru", "career.sibur.ru", "siberia.transneft.ru", "novatek.ru",
                  "gazpromvacancy.ru", "rosneft.ru", "avito.ru")
CITY_NAMES = ("Тюмень", "Нижневартовск")
BRANDS = ("СИБУР", "Транснефть", "НОВАТЭК", "Газпром", "Роснефть", "Другие компании")
BRAND_ALIASES = {
    "СИБУР": ("сибур", "запсибнефтехим", "сибуртобольск", "южно-балыкский гпз"),
    "Транснефть": ("транснефть",),
    "НОВАТЭК": ("новатэк", "новатек", "ямал спг", "арктик спг"),
    "Газпром": ("газпром", "газпромнефть", "газпром нефть"),
    "Роснефть": ("роснефть", "самотлорнефтегаз", "рн-уват", "рн-нягань", "рн-сервис", "рн-бурение", "рн-снабжение"),
}
SEARCH_TERMS = (
    "охрана труда", "промышленная безопасность", "производственная безопасность",
    "пожарная безопасность", "ПБОТОС", "HSE", "эколог", "техносферная",
    "ГО и ЧС", "ПЭБ", "ОТ и ПБ", "безопасность дорожного движения",
)
RELEVANT = re.compile(
    r"охран[аыуе]\s+труд|промышленн.{0,18}безопасност|"
    r"производственн.{0,18}безопасност|пожарн.{0,18}безопасност|"
    r"эколог|техносфер|гражданск.{0,12}оборон|"
    r"безопасност.{0,12}дорожн.{0,14}движ|"
    r"\b(?:пб|от|пэб|пботос|оти?пб|hse|ehs)\b",
    re.IGNORECASE,
)
IRRELEVANT = re.compile(
    r"информационн.{0,10}безопасност|экономическ.{0,10}безопасност|"
    r"кибербезопасност|служб[аые]\s+безопасност|"
    r"физическ.{0,10}охран|охранник",
    re.IGNORECASE,
)
RU_TIME = timezone(timedelta(hours=5))  # Tyumen/Nizhnevartovsk: fixed UTC+5


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


class TrackedVacancy(Base):
    __tablename__ = "tracked_vacancies"
    __table_args__ = (UniqueConstraint("source", "source_id", name="uq_tracked_vacancy_source"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source: Mapped[str] = mapped_column(String(30), default="hh.ru")
    source_id: Mapped[str] = mapped_column(String(64), nullable=False)
    brand: Mapped[str] = mapped_column(String(40), index=True)
    employer: Mapped[str] = mapped_column(String(255))
    title: Mapped[str] = mapped_column(String(500))
    city: Mapped[str] = mapped_column(String(80), index=True)
    url: Mapped[str] = mapped_column(String(500))
    salary: Mapped[str] = mapped_column(String(120), default="")
    schedule: Mapped[str] = mapped_column(String(120), default="")
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)


class VacancyScan(Base):
    __tablename__ = "vacancy_scans"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(24), default="running")
    found: Mapped[int] = mapped_column(Integer, default=0)
    message: Mapped[str] = mapped_column(Text, default="")


class VacancySourceSetting(Base):
    __tablename__ = "vacancy_source_settings"
    source: Mapped[str] = mapped_column(String(30), primary_key=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)


class VacancySourceStatus(Base):
    __tablename__ = "vacancy_source_status"
    source: Mapped[str] = mapped_column(String(30), primary_key=True)
    state: Mapped[str] = mapped_column(String(24), default="not_checked")
    found: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str] = mapped_column(Text, default="")
    checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


def disabled_source_names(db: Session) -> set[str]:
    return {
        name for name in db.scalars(
            select(VacancySourceSetting.source).where(VacancySourceSetting.enabled.is_(False))
        ) if name in SOURCES_FILTER
    }


def enabled_source_names(db: Session) -> tuple[str, ...]:
    excluded = disabled_source_names(db)
    return tuple(name for name in SOURCES_FILTER if name not in excluded)

def init_tables() -> None:
    Base.metadata.create_all(engine, tables=[TrackedVacancy.__table__, VacancyScan.__table__,
                                          VacancySourceSetting.__table__, VacancySourceStatus.__table__])


def company_brand(company: str) -> str | None:
    value = (company or "").casefold().replace("ё", "е")
    for brand, aliases in BRAND_ALIASES.items():
        if any(alias in value for alias in aliases):
            return brand
    return None


def relevant_title(title: str) -> bool:
    return bool(RELEVANT.search(title or "") and not IRRELEVANT.search(title or ""))


def parse_date(value: str) -> datetime:
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)
    except (ValueError, AttributeError):
        return now_utc()


def salary_text(value: dict | None) -> str:
    if not isinstance(value, dict):
        return ""
    start, end = value.get("from"), value.get("to")
    if start is None and end is None:
        return ""
    fmt = lambda n: f"{int(n):,}".replace(",", " ")
    if start is not None and end is not None:
        amount = f"{fmt(start)}–{fmt(end)}"
    elif start is not None:
        amount = f"от {fmt(start)}"
    else:
        amount = f"до {fmt(end)}"
    currency = "₽" if value.get("currency") == "RUR" else value.get("currency", "")
    return f"{amount} {currency}".strip()


def hh_json(endpoint: str, params: dict | None = None) -> dict | list:
    """Use registered hh.ru API; never bypass captcha or robots protection."""
    token = get_access_token()
    headers = {
        "HH-User-Agent": os.getenv("HH_USER_AGENT", "RPOVacancyMonitor/2.0 (rpo@rpo-mng.ru)"),
        "Accept": "application/json",
        "Authorization": f"Bearer {token}",
    }
    url = "https://api.hh.ru" + endpoint
    if params:
        url += "?" + urlencode(params)
    request = UrlRequest(url, headers=headers)
    try:
        with urlopen(request, timeout=20) as response:
            return json.load(response)
    except HTTPError as exc:
        hint = " Требуется действующий HH_API_TOKEN (OAuth) или доступ API." if exc.code in (401, 403, 429) else ""
        raise RuntimeError(f"HeadHunter API HTTP {exc.code}.{hint}") from exc
    except (URLError, TimeoutError) as exc:
        raise RuntimeError(f"Нет связи с HeadHunter API: {exc}") from exc


def area_ids() -> dict[str, str]:
    """Resolve IDs by current city names rather than relying on stale hardcoded IDs."""
    regions = hh_json("/areas")
    found: dict[str, str] = {}
    def walk(nodes):
        for node in nodes:
            name = node.get("name", "")
            if name in CITY_NAMES and not node.get("areas"):
                found[name] = str(node["id"])
            walk(node.get("areas") or [])
    walk(regions)
    if set(found) != set(CITY_NAMES):
        raise RuntimeError("Не найдены идентификаторы обоих городов в справочнике HH")
    return found


def parse_vacancy(item: dict, city: str) -> dict | None:
    if str((item.get("area") or {}).get("name", "")).casefold() != city.casefold():
        return None
    title = str(item.get("name", "")).strip()
    employer = str((item.get("employer") or {}).get("name", "")).strip()
    brand = company_brand(employer)
    identifier = str(item.get("id", ""))
    if not (title and identifier.isdigit()):
        return None
    brand = brand or "Другие компании"
    schedule = (item.get("schedule") or {}).get("name", "")
    return {
        "source": "hh.ru",
        "source_id": identifier,
        "brand": brand,
        "employer": employer[:255],
        "title": title[:500],
        "city": city,
        "url": "https://hh.ru/vacancy/" + identifier,
        "salary": salary_text(item.get("salary"))[:120],
        "schedule": str(schedule or "")[:120],
        "published_at": parse_date(item.get("published_at", "")),
    }


def fetch_current_vacancies() -> dict[str, dict]:
    """Fetch every published HH job in two cities within the last 30 days.

    HH caps one search at 2,000 records. Split the publication-date window
    whenever its size exceeds that limit. If the window cannot be exhausted,
    fail the source rather than inaccurately archiving unseen vacancies.
    """
    ids = area_ids()
    found: dict[str, dict] = {}
    end = now_utc()
    start = end - timedelta(days=30)

    def read_window(city: str, area_id: str, first: datetime, last: datetime, depth: int = 0):
        params = {
            "area": area_id,
            "per_page": 100,
            "page": 0,
            "order_by": "publication_time",
            "date_from": first.isoformat(timespec="seconds"),
            "date_to": last.isoformat(timespec="seconds"),
        }
        response = hh_json("/vacancies", params)
        pages = int(response.get("pages", 0))
        count = int(response.get("found", 0))
        if count > 2000 or pages > 20:
            if (last - first) <= timedelta(minutes=10) or depth >= 22:
                raise RuntimeError(f"HeadHunter: выдача {city} превышает лимит 2000 даже в минимальном интервале")
            mid = first + (last - first) / 2
            read_window(city, area_id, first, mid, depth + 1)
            read_window(city, area_id, mid, last, depth + 1)
            return
        for item in response.get("items", []):
            vacancy = parse_vacancy(item, city)
            if vacancy:
                found[vacancy["source_id"]] = vacancy
        for page in range(1, pages):
            params["page"] = page
            more = hh_json("/vacancies", params)
            for item in more.get("items", []):
                vacancy = parse_vacancy(item, city)
                if vacancy:
                    found[vacancy["source_id"]] = vacancy
            time.sleep(0.12)

    for city, area_id in ids.items():
        read_window(city, area_id, start, end)
    return found

def scan_once() -> tuple[str, int, str]:
    """Check enabled sources only; preserve the last good data on source errors."""
    from .vacancy_sources import collect_sources

    init_tables()
    with SessionLocal() as db:
        enabled = set(enabled_source_names(db))
        scan = VacancyScan(started_at=now_utc())
        db.add(scan)
        db.commit()
        scan_id = scan.id

    collected: dict[str, dict] = {}
    errors: dict[str, str] = {}
    if "hh.ru" in enabled:
        try:
            collected["hh.ru"] = fetch_current_vacancies()
        except Exception as exc:
            errors["hh.ru"] = str(exc)[:400]
            log.warning("HeadHunter scan failed: %s", exc)
    more, source_errors = collect_sources(enabled)
    collected.update(more)
    errors.update(source_errors)

    stamp = now_utc()
    total = 0
    with SessionLocal() as db:
        for source in SOURCES_FILTER:
            previous_status = db.get(VacancySourceStatus, source)
            if previous_status is None:
                previous_status = VacancySourceStatus(source=source)
                db.add(previous_status)
            if source not in enabled:
                previous_status.state = "excluded"
                previous_status.error = ""
                previous_status.found = 0
                previous_status.checked_at = stamp
                continue
            if source in errors:
                previous_status.state = "error"
                previous_status.error = errors[source]
                previous_status.checked_at = stamp
                # Retain the last successfully collected vacancy count.
                continue
            rows = collected.get(source, {})
            previous_status.state = "ok"
            previous_status.found = len(rows)
            previous_status.error = ""
            previous_status.checked_at = stamp
            existing = {
                v.source_id: v for v in db.scalars(
                    select(TrackedVacancy).where(TrackedVacancy.source == source)
                )
            }
            for ident, values in rows.items():
                vacancy = existing.get(ident)
                if vacancy is None:
                    db.add(TrackedVacancy(**values, first_seen_at=stamp, last_seen_at=stamp))
                else:
                    for key, value in values.items():
                        setattr(vacancy, key, value)
                    vacancy.active = True
                    vacancy.last_seen_at = stamp
            for ident, vacancy in existing.items():
                if ident not in rows:
                    vacancy.active = False
            total += len(rows)

        scan = db.get(VacancyScan, scan_id)
        if not enabled:
            scan.status = "excluded"
            scan.message = "Все источники исключены пользователем"
        elif errors and collected:
            scan.status = "partial"
            scan.message = "; ".join(
                f"{name}: {reason}" for name, reason in sorted(errors.items())
            )[:3500]
        elif errors:
            scan.status = "error"
            scan.message = "; ".join(
                f"{name}: {reason}" for name, reason in sorted(errors.items())
            )[:3500]
        else:
            scan.status = "ok"
            scan.message = ""
        scan.found = total
        scan.finished_at = stamp
        db.commit()
    return scan.status, total, scan.message

def ru_date(value: datetime | None) -> str:
    if not value:
        return "—"
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(RU_TIME).strftime("%d.%m.%Y %H:%M")


def query_vacancies(db: Session, brand: str = "", city: str = "", text: str = "", fresh: bool = False, page: int = 1, source: str = "", specialty: str = ""):
    query = select(TrackedVacancy).where(
        TrackedVacancy.active.is_(True), TrackedVacancy.source.in_(enabled_source_names(db))
    )
    if brand in BRANDS:
        query = query.where(TrackedVacancy.brand == brand)
    specialty_filter = specialty_condition(TrackedVacancy.title, specialty)
    if specialty_filter is not None:
        query = query.where(specialty_filter)
    if source in SOURCES_FILTER:
        query = query.where(TrackedVacancy.source == source)
    if city in CITY_NAMES:
        query = query.where(TrackedVacancy.city == city)
    if text:
        pattern = "%" + text.replace("%", r"\%").replace("_", r"\_") + "%"
        query = query.where(
            TrackedVacancy.title.ilike(pattern, escape="\\")
            | TrackedVacancy.employer.ilike(pattern, escape="\\")
        )
    if fresh:
        query = query.where(TrackedVacancy.first_seen_at >= now_utc() - timedelta(hours=24))
    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    vacancies = list(db.scalars(
        query.order_by(TrackedVacancy.published_at.desc(), TrackedVacancy.id.desc())
        .offset((page - 1) * 50).limit(50)
    ))
    return vacancies, total


@router.post("/vacancies/sources", include_in_schema=False)
def update_vacancy_sources(
    request: Request,
    excluded: Annotated[list[str] | None, Form()] = None,
    csrf_token: Annotated[str, Form()] = "",
    db: Session = Depends(get_db),
):
    from .vacancy_auth import vacancy_logged_in
    if not vacancy_logged_in(request):
        return RedirectResponse("/vacancies/login", status_code=303)
    expected = request.session.get("vacancies_source_csrf", "")
    if not expected or not hmac.compare_digest(expected, csrf_token):
        raise HTTPException(status_code=403, detail="Неверный токен формы")
    selected = set(excluded or [])
    if selected - set(SOURCES_FILTER):
        raise HTTPException(status_code=422, detail="Неизвестный источник вакансий")
    for source in SOURCES_FILTER:
        setting = db.get(VacancySourceSetting, source)
        if setting is None:
            setting = VacancySourceSetting(source=source)
            db.add(setting)
        setting.enabled = source not in selected
        setting.updated_at = now_utc()
    db.commit()
    return RedirectResponse("/vacancies?sources=updated", status_code=303)

@router.get("/vacancies", response_class=HTMLResponse, include_in_schema=False)
def vacancy_page(
    request: Request,
    brand: str = Query(default="", max_length=40),
    city: str = Query(default="", max_length=80),
    q: str = Query(default="", max_length=100),
    new: bool = Query(default=False),
    page: int = Query(default=1, ge=1, le=1000),
    source: str = Query(default="", max_length=30),
    specialty: str = Query(default="", max_length=40),
    db: Session = Depends(get_db),
):
    from .vacancy_auth import vacancy_logged_in
    if not vacancy_logged_in(request):
        return RedirectResponse("/vacancies/login", status_code=303)
    if not request.session.get("vacancies_source_csrf"):
        request.session["vacancies_source_csrf"] = secrets.token_urlsafe(24)
    operator = SimpleNamespace(username="admin")
    disabled_sources = disabled_source_names(db)
    vacancies, total = query_vacancies(db, brand, city, q.strip(), new, page, source, specialty)
    last_scan = db.scalar(select(VacancyScan).order_by(VacancyScan.id.desc()).limit(1))
    active_count = db.scalar(
        select(func.count()).select_from(TrackedVacancy).where(
            TrackedVacancy.active.is_(True), TrackedVacancy.source.in_(enabled_source_names(db))
        )
    ) or 0
    new_count = db.scalar(
        select(func.count()).select_from(TrackedVacancy).where(
            TrackedVacancy.active.is_(True),
            TrackedVacancy.source.in_(enabled_source_names(db)),
            TrackedVacancy.first_seen_at >= now_utc() - timedelta(hours=24),
        )
    ) or 0
    statuses = {v.source: v for v in db.scalars(select(VacancySourceStatus))}
    from .main_core import templates
    return templates.TemplateResponse(
        request=request, name="vacancies.html",
        context={
            "operator": operator, "vacancies": vacancies, "total": total,
            "active_count": active_count, "new_count": new_count, "scan": last_scan,
            "brands": BRANDS, "cities": CITY_NAMES,
            "specialties": SPECIALTIES, "specialty": specialty,
            "classify_specialty": classify_specialty,
            "sources": SOURCES_FILTER, "source": source,
            "disabled_sources": disabled_sources, "source_statuses": statuses,
            "source_csrf": request.session["vacancies_source_csrf"],
            "brand": brand, "city": city, "q": q, "new": new,
            "page": page, "page_count": (total + 49) // 50, "ru_date": ru_date,
            "new_since": now_utc() - timedelta(hours=24),
        },
        headers={"Cache-Control": "private, no-store"},
    )

"""Read-only vacancy monitoring, deliberately isolated from RPO operational data.

Job offers are retrieved from HeadHunter's official API, not scraped from
login-protected corporate websites. A separate worker performs hourly scans.
"""
from __future__ import annotations

import json
import hmac
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

from fastapi import APIRouter, Depends, Query, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import Boolean, DateTime, Integer, String, Text, UniqueConstraint, func, select
from sqlalchemy.orm import Mapped, Session, mapped_column

from .database import Base, SessionLocal, engine, get_db
from .security import verify_password

log = logging.getLogger("vacancies")
router = APIRouter()
DEFAULT_VACANCY_HASH = "$argon2id$v=19$m=65536,t=3,p=2$PHzNhBhkRwGqf3zcVPwRKg$TEvXaJFAtfrji6qKFfclzav/fyMGn1YbZgV6ecC6Oos"
# A salted password verifier, not plaintext; override via VACANCY_ADMIN_PASSWORD_HASH.
VACANCY_SESSION_HOURS = 8
AUTH_ATTEMPTS: dict[str, tuple[int, float]] = {}
SOURCES_FILTER = ("hh.ru", "career.sibur.ru", "siberia.transneft.ru", "novatek.ru",
                  "gazpromvacancy.ru", "rosneft.ru", "avito.ru")
CITY_NAMES = ("Тюмень", "Нижневартовск")
BRANDS = ("СИБУР", "Транснефть", "НОВАТЭК", "Газпром", "Роснефть")
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


def init_tables() -> None:
    Base.metadata.create_all(engine, tables=[TrackedVacancy.__table__, VacancyScan.__table__])


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
    token = os.getenv("HH_API_TOKEN", "").strip()
    headers = {
        "User-Agent": os.getenv("HH_USER_AGENT", "RPOVacancies/1.0 (rpo@rpo-mng.ru)"),
        "Accept": "application/json",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
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
    if not (brand and relevant_title(title) and identifier.isdigit()):
        return None
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
    ids = area_ids()
    found = {}
    for city, area_id in ids.items():
        for term in SEARCH_TERMS:
            for page in range(3):
                response = hh_json("/vacancies", {
                    "area": area_id,
                    "text": term,
                    "search_field": "name",
                    "per_page": 100,
                    "page": page,
                    "order_by": "publication_time",
                })
                for item in response.get("items", []):
                    vacancy = parse_vacancy(item, city)
                    if vacancy:
                        found[vacancy["source_id"]] = vacancy
                # Incomplete scans must not mark omitted vacancies as archived.
                if page + 1 >= int(response.get("pages", 0)):
                    break
                if page == 2:
                    raise RuntimeError(f"Неполная выдача HH: {city}, запрос «{term}»")
                time.sleep(0.25)
            time.sleep(0.25)
    return found


def scan_once() -> tuple[str, int, str]:
    """Refresh each source independently. A failed source keeps its previous data."""
    from .vacancy_sources import collect_sources
    init_tables()
    with SessionLocal() as db:
        scan = VacancyScan(started_at=now_utc())
        db.add(scan)
        db.commit()
        scan_id = scan.id
    collected = {}
    errors = {}
    try:
        collected["hh.ru"] = fetch_current_vacancies()
    except Exception as exc:
        errors["hh.ru"] = str(exc)[:180]
        log.warning("HeadHunter scan failed: %s", exc)
    more, source_errors = collect_sources()
    collected.update(more)
    errors.update(source_errors)
    stamp = now_utc()
    total = 0
    with SessionLocal() as db:
        for source, rows in collected.items():
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
        scan.status = "partial" if collected and errors else ("ok" if collected else "error")
        scan.found = total
        scan.finished_at = stamp
        scan.message = "; ".join(
            f"{name}: {reason}" for name, reason in sorted(errors.items())
        )[:3500]
        db.commit()
    return scan.status, total, scan.message

def ru_date(value: datetime | None) -> str:
    if not value:
        return "—"
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(RU_TIME).strftime("%d.%m.%Y %H:%M")


def query_vacancies(db: Session, brand: str = "", city: str = "", text: str = "", fresh: bool = False, page: int = 1, source: str = ""):
    query = select(TrackedVacancy).where(TrackedVacancy.active.is_(True))
    if brand in BRANDS:
        query = query.where(TrackedVacancy.brand == brand)
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


@router.get("/vacancies", response_class=HTMLResponse, include_in_schema=False)
def vacancy_page(
    request: Request,
    brand: str = Query(default="", max_length=40),
    city: str = Query(default="", max_length=80),
    q: str = Query(default="", max_length=100),
    new: bool = Query(default=False),
    page: int = Query(default=1, ge=1, le=1000),
    source: str = Query(default="", max_length=30),
    db: Session = Depends(get_db),
):
    from .vacancy_auth import vacancy_logged_in
    if not vacancy_logged_in(request):
        return RedirectResponse("/vacancies/login", status_code=303)
    operator = SimpleNamespace(username="admin")
    vacancies, total = query_vacancies(db, brand, city, q.strip(), new, page, source)
    last_scan = db.scalar(select(VacancyScan).order_by(VacancyScan.id.desc()).limit(1))
    active_count = db.scalar(
        select(func.count()).select_from(TrackedVacancy).where(TrackedVacancy.active.is_(True))
    ) or 0
    new_count = db.scalar(
        select(func.count()).select_from(TrackedVacancy).where(
            TrackedVacancy.active.is_(True),
            TrackedVacancy.first_seen_at >= now_utc() - timedelta(hours=24),
        )
    ) or 0
    from .main_core import templates
    return templates.TemplateResponse(
        request=request, name="vacancies.html",
        context={
            "operator": operator, "vacancies": vacancies, "total": total,
            "active_count": active_count, "new_count": new_count, "scan": last_scan,
            "brands": BRANDS, "cities": CITY_NAMES,
            "sources": SOURCES_FILTER, "source": source,
            "brand": brand, "city": city, "q": q, "new": new,
            "page": page, "page_count": (total + 49) // 50, "ru_date": ru_date,
            "new_since": now_utc() - timedelta(hours=24),
        },
        headers={"Cache-Control": "private, no-store"},
    )

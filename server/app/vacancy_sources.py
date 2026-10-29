"""Conservative official-career and Avito public-page collectors.

No proxy rotation, CAPTCHA solving, authentication circumvention or unpublished API.
Links are extracted only from allowlisted hosts and only for verifiable city/job data.
A robots.txt denial is a recorded source error, not an attempt to bypass protections.
"""
from __future__ import annotations

import hashlib
import logging
import os
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlparse, urlencode
from urllib.request import Request, urlopen
from urllib.robotparser import RobotFileParser

from bs4 import BeautifulSoup

log = logging.getLogger("vacancy-sources")
USER_AGENT = os.getenv("VACANCY_CRAWLER_UA", "RPOVacancyMonitor/1.0 (+https://rpo-mng.ru/vacancies)")
CITIES = ("Тюмень", "Нижневартовск")
JOBS = re.compile(r"охран[аыуе]\s+труд|промышленн.{0,18}безопасност|производственн.{0,18}безопасност|пожарн.{0,18}безопасност|эколог|техносфер|гражданск.{0,12}оборон|\b(?:пб|пэб|пботос|hse|ehs)\b", re.I)
EXCLUDE = re.compile(r"информационн.{0,15}безопасност|кибербезопасност|охранник|служб[аые]\s+безопасност", re.I)
URL_HREF = re.compile(r"vacan|career|job|rabot|position|dolzhn|vakansi", re.I)
AVITO_ITEM = re.compile(r"/(vakansii|vakansiya)/", re.I)
MAX_BYTES = 2_000_000


@dataclass(frozen=True)
class Source:
    name: str
    company: str
    pages: tuple[str, ...]
    allowed_host: str


SOURCES = (
    Source("career.sibur.ru", "СИБУР", ("https://career.sibur.ru/vacancies/",), "career.sibur.ru"),
    Source("siberia.transneft.ru", "Транснефть", ("https://siberia.transneft.ru/",), "siberia.transneft.ru"),
    Source("novatek.ru", "НОВАТЭК", ("https://www.novatek.ru/ru/about/career/jobs/",), "www.novatek.ru"),
    Source("gazpromvacancy.ru", "Газпром", (
        "https://www.gazpromvacancy.ru/vacancies/",
        "https://www.gazpromvacancy.ru/vacancies/region/tjumenskaja-oblast/",
        "https://www.gazpromvacancy.ru/vacancies/region/khmao-jugra/",
    ), "www.gazpromvacancy.ru"),
    Source("rosneft.ru", "Роснефть", ("https://www.rosneft.ru/about/career/",), "www.rosneft.ru"),
)
AVITO_SOURCE = "avito.ru"
AVITO_URLS = tuple(
    "https://www.avito.ru/" + loc + "/vakansii?" +
    urlencode({"q": "охрана труда"})  # public search, no cookies or challenge handling
    for loc in ("tyumen", "nizhnevartovsk")
)


def _read_page(url: str, *, max_bytes: int = MAX_BYTES) -> str:
    request = Request(url, headers={
        "User-Agent": USER_AGENT,
        "Accept": "text/html,application/xhtml+xml",
    })
    with urlopen(request, timeout=20) as response:
        final = response.geturl()
        if urlparse(final).hostname != urlparse(url).hostname:
            raise RuntimeError("Переадресация на другой домен: " + urlparse(final).hostname.__str__())
        mime = response.headers.get("Content-Type", "")
        if "text/html" not in mime and "text/plain" not in mime:
            raise RuntimeError("Ответ не является HTML")
        payload = response.read(max_bytes + 1)
        if len(payload) > max_bytes:
            raise RuntimeError("HTML превышает ограничение размера")
        encoding = response.headers.get_content_charset() or "utf-8"
        return payload.decode(encoding, errors="replace")


def _robots_allowed(url: str) -> None:
    host = urlparse(url).netloc
    robots_url = f"https://{host}/robots.txt"
    try:
        # Read robots even if it returns text/plain; never access a protected site
        # when robots.txt is unavailable.
        request = Request(robots_url, headers={"User-Agent": USER_AGENT})
        with urlopen(request, timeout=12) as response:
            if urlparse(response.geturl()).hostname != urlparse(url).hostname:
                raise RuntimeError("robots.txt перенаправлен на другой домен")
            content = response.read(150_000).decode("utf-8", errors="replace")
    except HTTPError as exc:
        if exc.code in (401, 403, 429):
            raise RuntimeError(f"robots.txt: HTTP {exc.code}; сбор пропущен") from exc
        if exc.code == 404:
            return  # Standard robots.txt convention: no restrictions on 404
        raise RuntimeError(f"robots.txt: HTTP {exc.code}") from exc
    except (URLError, OSError, TimeoutError) as exc:
        raise RuntimeError("robots.txt недоступен; сбор пропущен") from exc
    robots = RobotFileParser()
    robots.parse(content.splitlines())
    if not robots.can_fetch(USER_AGENT, url):
        raise RuntimeError("Сбор запрещён robots.txt")


def safe_url(page: str, href: str, allowed_host: str) -> str | None:
    if not href or href.startswith(("#", "javascript:", "mailto:", "tel:")):
        return None
    absolute = urljoin(page, href).split("#", 1)[0]
    parsed = urlparse(absolute)
    if parsed.scheme != "https" or parsed.hostname != allowed_host:
        return None
    return absolute


def slug_id(url: str) -> str:
    return hashlib.sha256(url.encode("utf-8")).hexdigest()


def _city(value: str) -> str | None:
    normalized = value.casefold().replace("ё", "е")
    for name in CITIES:
        if name.casefold() in normalized:
            return name
    return None


def _job(title: str) -> bool:
    return bool(JOBS.search(title) and not EXCLUDE.search(title))


def _listing_rows(html: str, page: str, source: Source) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    offers = []
    for anchor in soup.find_all("a", href=True):
        title = anchor.get_text(" ", strip=True)
        if len(title) < 8 or len(title) > 220 or not _job(title):
            continue
        url = safe_url(page, anchor["href"], source.allowed_host)
        if not url or not URL_HREF.search(urlparse(url).path):
            continue
        # Ancestor must include the city but not the whole page. Never infer
        # a location from the search-filter panel or from the employer HQ.
        city = None
        parent = anchor
        for _ in range(4):
            parent = parent.parent
            if parent is None or getattr(parent, "name", None) in {"body", "html"}:
                break
            nearby = parent.get_text(" ", strip=True)[:700]
            if len(nearby) > 900:
                break
            city = _city(nearby)
            if city:
                break
        if not city:
            continue
        employer = source.company
        offers.append({
            "source": source.name,
            "source_id": slug_id(url),
            "brand": source.company,
            "employer": employer,
            "title": title,
            "city": city,
            "url": url,
            "salary": "",
            "schedule": "",
            "published_at": datetime.now(timezone.utc),
        })
    return offers


def _novatek_rows(html: str, page: str) -> list[dict]:
    """NOVATEK publishes grouped vacancies as text on an official single page."""
    soup = BeautifulSoup(html, "html.parser")
    text = soup.get_text("\n", strip=True)
    blocks = re.split(r"(?=ООО\s+[«\"]?НОВАТЭК[^\n]{0,170}\(г\.\s*(?:Тюмень|Нижневартовск)\))", text, flags=re.I)
    offers = []
    for block in blocks[1:]:
        city = _city(block.split("\n", 1)[0])
        if not city:
            continue
        lines = [x.strip() for x in block.splitlines() if x.strip()]
        if len(lines) < 2:
            continue
        for index, line in enumerate(lines[1:20], 1):
            if _job(line) and len(line) < 180 and not line.startswith(("Требования", "Обязанности")):
                identifier = slug_id(page + city + line)
                offers.append({
                    "source": "novatek.ru", "source_id": identifier, "brand": "НОВАТЭК",
                    "employer": lines[0][:255], "title": line, "city": city, "url": page,
                    "salary": "", "schedule": "", "published_at": datetime.now(timezone.utc),
                })
    return offers


def fetch_official(source: Source) -> dict[str, dict]:
    result = {}
    for page in source.pages:
        _robots_allowed(page)
        html = _read_page(page)
        found = _novatek_rows(html, page) if source.name == "novatek.ru" else _listing_rows(html, page, source)
        for vacancy in found:
            result[vacancy["source_id"]] = vacancy
    return result


def _avito_rows(html: str, page: str, city: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    rows = {}
    for card in soup.select('[data-marker="item"]'):
        a = card.select_one('a[data-marker="item-title"][href]') or card.select_one("a[href*='/vakansii/']")
        if a is None:
            continue
        title = a.get_text(" ", strip=True)
        if not _job(title):
            continue
        href = safe_url(page, a.get("href", ""), "www.avito.ru")
        if not href or not AVITO_ITEM.search(urlparse(href).path):
            continue
        card_text = card.get_text(" ", strip=True)
        if city.casefold() not in card_text.casefold():
            continue
        # Unlike named company career portals, Avito ads are independently
        # authored. Only an explicitly attributable company is accepted.
        from .vacancies import company_brand
        brand = company_brand(card_text)
        if not brand:
            continue
        rows[slug_id(href)] = {
            "source": AVITO_SOURCE, "source_id": slug_id(href), "brand": brand,
            "employer": "На Авито указано: " + brand + " (не подтверждено)", "title": title[:500], "city": city, "url": href,
            "salary": "", "schedule": "", "published_at": datetime.now(timezone.utc),
        }
    return list(rows.values())


def fetch_avito() -> dict[str, dict]:
    # Public pages only. Avito Job API is designed for the employer's own ads
    # and cannot legitimately be used to search all other companies' ads.
    result = {}
    for city, page in zip(CITIES, AVITO_URLS):
        _robots_allowed(page)
        html = _read_page(page)
        for entry in _avito_rows(html, page, city):
            result[entry["source_id"]] = entry
    return result


def collect_sources(enabled: set[str] | None = None) -> tuple[dict[str, dict[str, dict]], dict[str, str]]:
    """Each source is isolated. An inaccessible site does not block other sites."""
    collected = {}
    errors = {}
    for source in SOURCES:
        if enabled is not None and source.name not in enabled:
            continue
        try:
            collected[source.name] = fetch_official(source)
        except (HTTPError, URLError, TimeoutError, ValueError, RuntimeError, OSError) as exc:
            errors[source.name] = str(exc)[:180]
            log.warning("Official source %s failed: %s", source.name, exc)
    if enabled is None or AVITO_SOURCE in enabled:
        try:
            collected[AVITO_SOURCE] = fetch_avito()
        except (HTTPError, URLError, TimeoutError, ValueError, RuntimeError, OSError) as exc:
            errors[AVITO_SOURCE] = str(exc)[:180]
            log.warning("Avito source unavailable: %s", exc)
    return collected, errors

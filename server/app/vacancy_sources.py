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
import time
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
_ROBOTS_CACHE: dict[str, tuple[float, str | None]] = {}
_ROBOTS_TTL = 24 * 3600


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
    """Check robots per RFC 9309: 404/410 are unavailable, 5xx/network are unreachable.

    Never bypass explicit Disallow, authentication blocks or rate limits.
    Retain a successful rule set for up to 24 hours on temporary failures.
    """
    host = urlparse(url).netloc
    stamp = time.monotonic()
    cached = _ROBOTS_CACHE.get(host)
    rules: str | None = None
    if cached and stamp - cached[0] < _ROBOTS_TTL:
        rules = cached[1]
    else:
        robots_url = f"https://{host}/robots.txt"
        try:
            request = Request(robots_url, headers={"User-Agent": USER_AGENT})
            with urlopen(request, timeout=12) as response:
                final = response.geturl()
                if urlparse(final).hostname != urlparse(url).hostname:
                    raise RuntimeError("robots.txt: перенаправление на другой домен; сбор пропущен")
                rules = response.read(512_001).decode("utf-8", errors="replace")
                if len(rules) > 512_000:
                    raise RuntimeError("robots.txt: слишком большой файл")
        except HTTPError as exc:
            if exc.code in (404, 410):
                rules = None  # RFC 9309: no robots at these paths -> unavailable
            elif exc.code in (401, 403, 429):
                raise RuntimeError(f"robots.txt: доступ ограничен HTTP {exc.code}; сбор пропущен") from exc
            else:
                if cached and stamp - cached[0] < _ROBOTS_TTL:
                    rules = cached[1]
                else:
                    raise RuntimeError(f"robots.txt: HTTP {exc.code}; сбор пропущен") from exc
        except (URLError, OSError, TimeoutError) as exc:
            if cached and stamp - cached[0] < _ROBOTS_TTL:
                rules = cached[1]
            else:
                raise RuntimeError("robots.txt: временно недоступен по сети; сбор пропущен") from exc
        _ROBOTS_CACHE[host] = (stamp, rules)
    if rules is None:
        return
    parser = RobotFileParser()
    parser.parse(rules.splitlines())
    if not parser.can_fetch(USER_AGENT, url):
        raise RuntimeError("Сбор запрещён robots.txt")


# Index pages, regional navigation and directory URLs must not become jobs.
NON_JOB_LABELS = re.compile(
    r"^(?:все вакансии|найти вакансию|поиск вакансий|подробнее|"
    r"тюмень|нижневартовск|тобольск|нижний новгород|нижнекамск|"
    r"москва|санкт-петербург|казань|уфа|пермь|работа в|"
    r"вакансии в|открытые вакансии|производство|бэк-офис|"
    r"строительство|наука|маркетинг и продажи|работа|карьера)$", re.I
)
NON_JOB_PATHS = re.compile(
    r"^(?:vacancies|vacancy|career|jobs?|cities|city|regions?|"
    r"locations?|tobolsk|tyumen|nizhnevartovsk|nizhnekamsk|"
    r"nizhniy-novgorod|nizhny-novgorod|moscow|kazan|ufa)$", re.I
)
JOB_WORDS = re.compile(
    r"инженер|специалист|эксперт|мастер|оператор|механик|"
    r"начальник|руководитель|директор|технолог|лаборант|"
    r"водитель|слесарь|электромонт|бухгалтер|аналитик|"
    r"менеджер|экономист|юрист|геолог|химик|машинист|"
    r"программист|разработчик|стажер|стажёр|рабочий|"
    r"контролер|контролёр|электрик|сварщик|аппаратчик", re.I
)


def looks_like_job(title: str, url: str, listing_page: str) -> bool:
    """Fail closed for broad category/city links, even when they contain a city nearby."""
    title = " ".join(title.split()).strip(" –—•")
    if not 6 <= len(title) <= 160 or NON_JOB_LABELS.search(title):
        return False
    if not JOB_WORDS.search(title):
        return False
    dest = urlparse(url)
    base = urlparse(listing_page)
    if dest.scheme != "https" or dest.hostname != base.hostname:
        return False
    if dest.path.rstrip("/") == base.path.rstrip("/"):
        return False
    bits = [part.lower() for part in dest.path.strip("/").split("/") if part]
    if not bits or NON_JOB_PATHS.fullmatch(bits[-1]):
        return False
    if any(item in ("cities", "city", "locations", "regions") for item in bits):
        return False
    if not URL_HREF.search(dest.path):
        return False
    # A generic page with a location/category as the last component is not a job.
    return True


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
    """Collect only identifiable job-detail links with an explicit local city."""
    soup = BeautifulSoup(html, "html.parser")
    offers: list[dict] = []
    seen: set[str] = set()
    for anchor in soup.find_all("a", href=True):
        if anchor.find_parent(["nav", "header", "footer"]):
            continue
        title = " ".join(anchor.get_text(" ", strip=True).split())
        url = safe_url(page, anchor["href"], source.allowed_host)
        if not url or not looks_like_job(title, url, page):
            continue
        city = None
        parent = anchor
        for _ in range(4):
            parent = parent.parent
            if parent is None or getattr(parent, "name", None) in {"body", "html", "nav"}:
                break
            nearby = parent.get_text(" ", strip=True)
            if len(nearby) > 450:
                break
            city = _city(nearby)
            if city:
                break
        if not city or url in seen:
            continue
        seen.add(url)
        offers.append({
            "source": source.name,
            "source_id": slug_id(url),
            "brand": source.company,
            "employer": source.company,
            "title": title,
            "city": city,
            "url": url,
            "salary": "",
            "schedule": "",
            "published_at": datetime.now(timezone.utc),
        })
    return offers



def _novatek_rows(html: str, page: str) -> list[dict]:
    """Read only real job headings on NOVATEK career page, never job-description text.

    The public page groups a company and location header followed by a job
    title and its experience/duties/requirements. Its paragraphs and list items
    are not separate vacancies. There is no verified publication timestamp.
    """
    soup = BeautifulSoup(html, "html.parser")
    for unwanted in soup(["script", "style", "noscript"]):
        unwanted.decompose()
    text = soup.get_text("\n", strip=True)
    # Each employer heading explicitly states the city. A header is not a
    # vacancy until it is followed by a plausible job title + job-specific facts.
    company_heading = re.compile(
        r"(?=ООО\s+[«\"]?НОВАТЭК[^\n]{0,170}\(г\.\s*(?:Тюмень|Нижневартовск)\))",
        re.I,
    )
    bad_title = re.compile(
        r"^(?:важное уточнение|обязанности|требования|требуемый опыт|"
        r"условия|полная занятость|необходимые знания|документирование|"
        r"управление проектами\s*:|ключевые задачи|контакты|"
        r"глубокие экспертные знания)", re.I,
    )
    offers: list[dict] = []
    unique: set[str] = set()
    blocks = company_heading.split(text)
    for block in blocks[1:]:
        lines = [line.strip() for line in block.splitlines() if line.strip()]
        if len(lines) < 3:
            continue
        employer = lines[0]
        city = _city(employer)
        if not city:
            continue
        # The position is the FIRST text after the employer header, never
        # subsequent duties, bullet points or explanatory paragraphs.
        title = lines[1].strip(" \t–—•")
        if (not 8 <= len(title) <= 150 or len(title.split()) < 2
                or title.endswith(":") or bad_title.search(title)):
            continue
        # A job title must be backed by nearby vacancy metadata, not just by
        # the employer being mentioned in a general article/footer.
        context = " ".join(lines[2:9]).casefold()
        if not any(marker in context for marker in (
            "требуемый опыт", "занятость", "обязанности", "требования",
            "условия работы", "опыт работы",
        )):
            continue
        ident = slug_id(page + "|" + employer.casefold() + "|" + title.casefold())
        if ident in unique:
            continue
        unique.add(ident)
        offers.append({
            "source": "novatek.ru", "source_id": ident, "brand": "НОВАТЭК",
            "employer": employer[:255], "title": title, "city": city,
            "url": page, "salary": "", "schedule": "",
            # The official page does not state a publication date. This
            # placeholder is only for database ordering, not for UI display.
            "published_at": datetime.now(timezone.utc),
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
        if len(title) < 6:
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
        brand = company_brand(card_text) or "Другие компании"
        rows[slug_id(href)] = {
            "source": AVITO_SOURCE, "source_id": slug_id(href), "brand": brand,
            "employer": "Работодатель по объявлению (не проверен)" if brand == "Другие компании" else "На Авито указано: " + brand + " (не подтверждено)", "title": title[:500], "city": city, "url": href,
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

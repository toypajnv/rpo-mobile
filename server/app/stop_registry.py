from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import re
import unicodedata
from pathlib import Path

from pyxlsb import open_workbook
from sqlalchemy import DateTime, Integer, String, Text, delete, func, select
from sqlalchemy.orm import Mapped, Session, mapped_column

from .database import Base

EXCEL_EPOCH = datetime(1899, 12, 30)
PASS_TOKEN_RE = re.compile(r"\d{2,8}(?:-\d{1,8})?[A-ZА-Я]?", re.IGNORECASE)
CYR_LOOKALIKES = str.maketrans({"А": "A", "С": "C", "а": "A", "с": "C"})


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class StopRegistryRecord(Base):
    __tablename__ = "stop_registry_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    pass_number: Mapped[str] = mapped_column(String(40), index=True)
    pass_raw: Mapped[str] = mapped_column(String(120), default="")
    record_date: Mapped[str] = mapped_column(String(20), default="", index=True)
    fio: Mapped[str] = mapped_column(String(240), default="")
    company: Mapped[str] = mapped_column(String(300), default="")
    stop_reason: Mapped[str] = mapped_column(Text, default="")
    measures: Mapped[str] = mapped_column(Text, default="")
    report_status: Mapped[str] = mapped_column(String(40), default="")
    course_name: Mapped[str] = mapped_column(String(300), default="")
    course_status: Mapped[str] = mapped_column(String(40), default="")
    pkm_status: Mapped[str] = mapped_column(String(40), default="")
    access_status: Mapped[str] = mapped_column(String(40), default="", index=True)
    source_row: Mapped[int] = mapped_column(Integer)
    imported_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)


class StopContractRecord(Base):
    __tablename__ = "stop_contract_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company: Mapped[str] = mapped_column(String(300), default="", index=True)
    contract_number: Mapped[str] = mapped_column(String(160), default="", index=True)
    contract_owner: Mapped[str] = mapped_column(String(240), default="")
    eol: Mapped[str] = mapped_column(String(240), default="")
    deputy_eol: Mapped[str] = mapped_column(String(240), default="")
    contract_engineer: Mapped[str] = mapped_column(String(240), default="")
    reserve_engineer: Mapped[str] = mapped_column(String(240), default="")
    hse: Mapped[str] = mapped_column(String(240), default="")
    onsite_contact: Mapped[str] = mapped_column(String(240), default="")
    valid_until: Mapped[str] = mapped_column(String(80), default="")
    risk_level: Mapped[str] = mapped_column(String(120), default="")
    criticality: Mapped[str] = mapped_column(String(120), default="")
    source_row: Mapped[int] = mapped_column(Integer, default=0)
    imported_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)


class StopRegistryImport(Base):
    __tablename__ = "stop_registry_imports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    file_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    file_name: Mapped[str] = mapped_column(String(255), default="")
    message_id: Mapped[str] = mapped_column(String(500), default="", index=True)
    sender: Mapped[str] = mapped_column(String(320), default="")
    source_rows: Mapped[int] = mapped_column(Integer, default=0)
    indexed_rows: Mapped[int] = mapped_column(Integer, default=0)
    unique_passes: Mapped[int] = mapped_column(Integer, default=0)
    imported_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)


@dataclass(frozen=True)
class ParsedStopRecord:
    pass_number: str
    pass_raw: str
    record_date: str
    fio: str
    company: str
    stop_reason: str
    measures: str
    report_status: str
    course_name: str
    course_status: str
    pkm_status: str
    access_status: str
    source_row: int


@dataclass(frozen=True)
class ImportResult:
    duplicate: bool
    source_rows: int
    indexed_rows: int
    unique_passes: int
    file_hash: str


def _text(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value).strip()


def normalize_pass_number(value: object) -> str:
    raw = unicodedata.normalize("NFKC", _text(value)).strip().upper()
    # Remove human-readable labels before replacing Cyrillic lookalike letters in the pass itself.
    raw = re.sub(r"ПРОПУСК", "", raw, flags=re.IGNORECASE).strip()
    # NFKC expands the numero sign № to "No", so accept № / No / Номер prefixes equally.
    raw = re.sub(r"^(?:N[OО]\.?|НОМЕР)\s*", "", raw, flags=re.IGNORECASE)
    raw = raw.translate(CYR_LOOKALIKES)
    raw = raw.replace("№", " ").replace('"', " ").replace("'", " ")
    raw = re.sub(r"\s+", "", raw)
    match = PASS_TOKEN_RE.fullmatch(raw)
    return match.group(0).translate(CYR_LOOKALIKES).upper() if match else ""


def extract_pass_numbers(value: object) -> list[str]:
    raw = unicodedata.normalize("NFKC", _text(value)).upper()
    if not raw:
        return []
    direct = normalize_pass_number(raw)
    if direct:
        return [direct]
    tokens: list[str] = []
    for match in PASS_TOKEN_RE.finditer(raw):
        token = normalize_pass_number(match.group(0))
        if token and token not in tokens:
            tokens.append(token)
    return tokens


def excel_date(value: object) -> str:
    if isinstance(value, (int, float)):
        return (EXCEL_EPOCH + timedelta(days=float(value))).date().isoformat()
    return _text(value)


def _header(value: object) -> str:
    return re.sub(r"\s+", " ", _text(value).upper().replace("Ё", "Е")).strip()


def _validate_registry_headers(row5: list[object], row8: list[object]) -> None:
    def value(row: list[object], number: int) -> str:
        return _header(row[number - 1] if len(row) >= number else None)

    expected = (
        (value(row8, 19), "ПРОПУСКА ПЕРСОНАЛА", "№ пропуска персонала"),
        (value(row5, 27), "ОТЧЕТ ОБ УСТРАНЕНИИ", "Отчет об устранении"),
        (value(row5, 30), "КУРС", "Назначенные курсы"),
        (value(row5, 31), "КУРС ПРОЙДЕН", "Курс пройден"),
        (value(row5, 32), "ПКМ", "ПКМ"),
        (value(row5, 33), "ДОСТУП", "Доступ"),
    )
    missing = [label for actual, marker, label in expected if marker not in actual]
    if missing:
        raise ValueError("Структура листа СВОД изменилась. Не найдены колонки: " + ", ".join(missing))


def parse_registry(path: str | Path) -> tuple[list[ParsedStopRecord], int]:
    records: list[ParsedStopRecord] = []
    source_rows = 0
    row5: list[object] = []
    with open_workbook(str(path)) as workbook:
        if "СВОД" not in workbook.sheets:
            raise ValueError('В файле отсутствует лист "СВОД"')
        with workbook.get_sheet("СВОД") as sheet:
            for row_index, row in enumerate(sheet.rows(), start=1):
                values = [cell.v for cell in row]
                if row_index == 5:
                    row5 = values
                if row_index == 8:
                    _validate_registry_headers(row5, values)
                if row_index <= 8:
                    continue
                if not any(value not in (None, "") for value in values):
                    continue
                source_rows += 1

                def col(number: int):
                    return values[number - 1] if len(values) >= number else None

                raw_pass = _text(col(19))
                pass_numbers = extract_pass_numbers(col(19))
                if not pass_numbers:
                    continue
                for pass_number in pass_numbers:
                    records.append(
                        ParsedStopRecord(
                            pass_number=pass_number,
                            pass_raw=raw_pass,
                            record_date=excel_date(col(2)),
                            fio=_text(col(16)),
                            company=_text(col(10)),
                            stop_reason=_text(col(15)),
                            measures=_text(col(24)),
                            report_status=_text(col(27)),
                            course_name=_text(col(30)),
                            course_status=_text(col(31)),
                            pkm_status=_text(col(32)),
                            access_status=_text(col(33)),
                            source_row=row_index,
                        )
                    )
    if not records:
        raise ValueError("В реестре не найдено ни одного номера пропуска персонала")
    return records, source_rows


def parse_contract_directory(path: str | Path) -> list[dict]:
    """Read the optional contract directory without depending on fixed column numbers."""
    aliases = {
        "company": ("ПОДРЯД", "ОРГАНИЗАЦ"),
        "contract_number": ("ДОГОВОР",),
        "contract_owner": ("ВЛАДЕЛ", "ДОГОВОР"),
        "eol": ("ЕОЛ",),
        "deputy_eol": ("ЗАМЕЩ", "ЕОЛ"),
        "contract_engineer": ("КОНТРАКТ", "ИНЖЕНЕР"),
        "reserve_engineer": ("РЕЗЕРВ", "ИНЖЕНЕР"),
        "hse": ("HSE",),
        "onsite_contact": ("ИСПОЛНИТ", "МЕСТ"),
        "valid_until": ("СРОК", "ДЕЙСТВ"),
        "risk_level": ("УРОВ", "РИСК"),
        "criticality": ("КРИТИЧ",),
    }

    def match_index(headers: list[str], parts: tuple[str, ...], *, exclude: tuple[str, ...] = ()) -> int | None:
        for idx, header in enumerate(headers):
            if all(part in header for part in parts) and not any(word in header for word in exclude):
                return idx
        return None

    try:
        with open_workbook(str(path)) as workbook:
            sheet_name = next((name for name in workbook.sheets if "ДОГОВ" in _header(name)), "")
            if not sheet_name:
                return []
            rows = []
            with workbook.get_sheet(sheet_name) as sheet:
                header_row_index = 0
                header_values: list[str] = []
                raw_rows: list[tuple[int, list[object]]] = []
                for row_index, row in enumerate(sheet.rows(), start=1):
                    values = [cell.v for cell in row]
                    raw_rows.append((row_index, values))
                    normalized = [_header(value) for value in values]
                    joined = " | ".join(normalized)
                    if row_index <= 25 and "ПОДРЯД" in joined and ("ДОГОВОР" in joined or "ЕОЛ" in joined):
                        header_row_index = row_index
                        header_values = normalized
                        break
                if not header_row_index:
                    return []

                indexes = {
                    "company": match_index(header_values, aliases["company"]),
                    "contract_number": match_index(header_values, aliases["contract_number"], exclude=("ВЛАДЕЛ",)),
                    "contract_owner": match_index(header_values, aliases["contract_owner"]),
                    "deputy_eol": match_index(header_values, aliases["deputy_eol"]),
                    "contract_engineer": match_index(header_values, aliases["contract_engineer"], exclude=("РЕЗЕРВ",)),
                    "reserve_engineer": match_index(header_values, aliases["reserve_engineer"]),
                    "hse": match_index(header_values, aliases["hse"]),
                    "onsite_contact": match_index(header_values, aliases["onsite_contact"]),
                    "valid_until": match_index(header_values, aliases["valid_until"]),
                    "risk_level": match_index(header_values, aliases["risk_level"]),
                    "criticality": match_index(header_values, aliases["criticality"]),
                }
                # EOL must not accidentally resolve to "замещающий ЕОЛ".
                indexes["eol"] = next(
                    (idx for idx, header in enumerate(header_values) if "ЕОЛ" in header and "ЗАМЕЩ" not in header),
                    None,
                )
                if indexes["company"] is None:
                    return []

                # Re-open so rows after the discovered header are streamed normally.
            with workbook.get_sheet(sheet_name) as sheet:
                for row_index, row in enumerate(sheet.rows(), start=1):
                    if row_index <= header_row_index:
                        continue
                    values = [cell.v for cell in row]
                    def value(key: str) -> str:
                        idx = indexes.get(key)
                        return _text(values[idx]) if idx is not None and idx < len(values) else ""
                    company = value("company")
                    if not company:
                        continue
                    rows.append({
                        "company": company,
                        "contract_number": value("contract_number"),
                        "contract_owner": value("contract_owner"),
                        "eol": value("eol"),
                        "deputy_eol": value("deputy_eol"),
                        "contract_engineer": value("contract_engineer"),
                        "reserve_engineer": value("reserve_engineer"),
                        "hse": value("hse"),
                        "onsite_contact": value("onsite_contact"),
                        "valid_until": value("valid_until"),
                        "risk_level": value("risk_level"),
                        "criticality": value("criticality"),
                        "source_row": row_index,
                    })
            return rows
    except Exception:
        # Contract data is useful context, but must never break the safety registry import.
        return []


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def import_registry(
    db: Session,
    path: str | Path,
    *,
    file_name: str = "",
    message_id: str = "",
    sender: str = "",
) -> ImportResult:
    file_hash = sha256_file(path)
    previous = db.scalar(select(StopRegistryImport).where(StopRegistryImport.file_hash == file_hash))
    if previous:
        # A repeated file can backfill the contract directory after this feature was introduced.
        if not (db.scalar(select(func.count(StopContractRecord.id))) or 0):
            contracts = parse_contract_directory(path)
            if contracts:
                imported_at = utcnow()
                db.add_all(
                    StopContractRecord(
                        company=item["company"],
                        contract_number=item["contract_number"],
                        contract_owner=item["contract_owner"],
                        eol=item["eol"],
                        deputy_eol=item["deputy_eol"],
                        contract_engineer=item["contract_engineer"],
                        reserve_engineer=item["reserve_engineer"],
                        hse=item["hse"],
                        onsite_contact=item["onsite_contact"],
                        valid_until=item["valid_until"],
                        risk_level=item["risk_level"],
                        criticality=item["criticality"],
                        source_row=item["source_row"],
                        imported_at=imported_at,
                    )
                    for item in contracts
                )
                db.commit()
        return ImportResult(True, previous.source_rows, previous.indexed_rows, previous.unique_passes, file_hash)

    parsed, source_rows = parse_registry(path)
    contracts = parse_contract_directory(path)
    imported_at = utcnow()
    db.execute(delete(StopRegistryRecord))
    db.execute(delete(StopContractRecord))
    db.add_all(
        StopRegistryRecord(
            pass_number=item.pass_number,
            pass_raw=item.pass_raw,
            record_date=item.record_date,
            fio=item.fio,
            company=item.company,
            stop_reason=item.stop_reason,
            measures=item.measures,
            report_status=item.report_status,
            course_name=item.course_name,
            course_status=item.course_status,
            pkm_status=item.pkm_status,
            access_status=item.access_status,
            source_row=item.source_row,
            imported_at=imported_at,
        )
        for item in parsed
    )
    if contracts:
        db.add_all(
            StopContractRecord(
                company=item["company"],
                contract_number=item["contract_number"],
                contract_owner=item["contract_owner"],
                eol=item["eol"],
                deputy_eol=item["deputy_eol"],
                contract_engineer=item["contract_engineer"],
                reserve_engineer=item["reserve_engineer"],
                hse=item["hse"],
                onsite_contact=item["onsite_contact"],
                valid_until=item["valid_until"],
                risk_level=item["risk_level"],
                criticality=item["criticality"],
                source_row=item["source_row"],
                imported_at=imported_at,
            )
            for item in contracts
        )

    unique_passes = len({item.pass_number for item in parsed})
    db.add(
        StopRegistryImport(
            file_hash=file_hash,
            file_name=file_name or Path(path).name,
            message_id=message_id[:500],
            sender=sender[:320],
            source_rows=source_rows,
            indexed_rows=len(parsed),
            unique_passes=unique_passes,
            imported_at=imported_at,
        )
    )
    db.commit()
    return ImportResult(False, source_rows, len(parsed), unique_passes, file_hash)


def _upper(value: str) -> str:
    return (value or "").strip().upper().replace("Ё", "Е")


def _yes_no_required(value: str) -> str:
    normalized = _upper(value)
    if normalized in {"ДА", "YES"}:
        return "yes"
    if normalized in {"НЕТ", "NO"}:
        return "no"
    if "НЕ ТРЕБУЕТ" in normalized:
        return "not_required"
    return "unknown"


def _access(value: str) -> str:
    normalized = _upper(value)
    if "ЗАПРЕЩ" in normalized:
        return "denied"
    if "РАЗРЕШ" in normalized:
        return "allowed"
    return "unknown"


def _requirements(record: StopRegistryRecord) -> list[dict]:
    report_state = _yes_no_required(record.report_status)
    course_state = _yes_no_required(record.course_status)
    pkm_state = _yes_no_required(record.pkm_status)
    course_name = (record.course_name or "").strip()
    if "НЕ ТРЕБУЕТ" in _upper(course_name):
        course_name = ""

    report_ok = report_state in {"yes", "not_required"}
    course_ok = course_state in {"yes", "not_required"}
    pkm_ok = pkm_state in {"yes", "not_required"}

    return [
        {
            "key": "report",
            "label": "Отчет об устранении",
            "state": "ok" if report_ok else "required",
            "value": "Предоставлен / не требуется" if report_ok else "Необходимо предоставить",
        },
        {
            "key": "course",
            "label": "Курс обучения",
            "state": "ok" if course_ok else "required",
            "value": "Пройден / не требуется" if course_ok else "Не пройден" + (f": {course_name}" if course_name else ""),
        },
        {
            "key": "pkm",
            "label": "ПКМ",
            "state": "ok" if pkm_ok else "required",
            "value": "Предоставлен / не требуется" if pkm_ok else "Необходимо предоставить",
        },
    ]


def lookup_pass(db: Session, pass_input: str) -> dict:
    pass_number = normalize_pass_number(pass_input)
    if not pass_number:
        raise ValueError("Введите корректный номер пропуска")

    # The registry contains history. Only the latest row defines the current state:
    # newest date first, and for equal dates the lower sheet row is superseded by the later row.
    record = db.scalar(
        select(StopRegistryRecord)
        .where(StopRegistryRecord.pass_number == pass_number)
        .order_by(StopRegistryRecord.record_date.desc(), StopRegistryRecord.source_row.desc())
        .limit(1)
    )
    if record is None:
        return {
            "pass_number": pass_number,
            "status": "allowed",
            "title": "Доступ разрешен",
            "message": "Номер пропуска отсутствует в действующем реестре ограничений.",
            "requirements": [],
        }

    access = _access(record.access_status)
    if access == "allowed":
        return {
            "pass_number": pass_number,
            "status": "allowed",
            "title": "Доступ разрешен",
            "message": "По последней записи реестра доступ разрешен.",
            "requirements": [],
        }

    if access == "unknown":
        return {
            "pass_number": pass_number,
            "status": "denied",
            "title": "Доступ запрещен",
            "message": "Статус допуска не определен в последней записи реестра. Обратитесь к ответственному лицу.",
            "requirements": _requirements(record),
        }

    return {
        "pass_number": pass_number,
        "status": "denied",
        "title": "Доступ запрещен",
        "message": "Для снятия ограничения проверьте требования ниже.",
        "requirements": _requirements(record),
    }

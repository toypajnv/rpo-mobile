from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import re
import unicodedata
from pathlib import Path

from pyxlsb import open_workbook
from sqlalchemy import DateTime, Integer, String, Text, delete, select
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
    # Remove the human label before replacing Cyrillic lookalike letters in the pass itself.
    raw = re.sub(r"ПРОПУСК", "", raw, flags=re.IGNORECASE)
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
        return ImportResult(True, previous.source_rows, previous.indexed_rows, previous.unique_passes, file_hash)

    parsed, source_rows = parse_registry(path)
    imported_at = utcnow()
    db.execute(delete(StopRegistryRecord))
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

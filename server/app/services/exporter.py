from __future__ import annotations

from datetime import date, datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo
import json

from openpyxl import Workbook
from openpyxl.formatting.rule import FormulaRule
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.worksheet.datavalidation import DataValidation
from openpyxl.worksheet.table import Table, TableStyleInfo

from ..models import PermitRecord
from ..stages import STAGES


MOSCOW_TZ = ZoneInfo("Europe/Moscow")
MAX_TEMPLATE_LAST_ROW = 501

MAX_HEADERS = [
    "Признак НД (новый/продленный)",
    "Продлён до (дата)",
    "Номер наряда-допуска",
    "Дата и время начала подготовки (технологию не учитываем)",
    "Дата и время окончания подготовки",
    "Дата и время передачи ОП к ОБПР",
    "Допуск исполнителей\n(уточнение по исполнителям и произведенным заменам)\nда/нет\nне критично",
    'Дата и время допуска со стороны "допускающего" (ГСС, ПЧ, Допускающий при ВРР)',
    "Дата и время начала факт проведения",
    "Дата и врем остановки",
    "Дата и время возобновления",
    "Причина остановки",
    "Дата и время фактического завершения РПО ",
    "Дата и время выполнения мероприятий по завершению работ \nсогласно НД",
    "Продление РПО ",
    "Дата и время выполнения мероприятий по передаче объекта согласно НД",
    "Закрытие ЭНД ",
    "дата и время передачи площадки эксплуатирующей организации",
    "Своевременное сообщение по завершению работ Да/нет",
    "Наряд допук-подгружен в течении 24 ч.\nда/нет",
    "Видеозаписи выложены в папку",
]

COLUMN_WIDTHS = {
    "A": 22,
    "B": 17,
    "C": 20,
    "D": 27,
    "E": 25,
    "F": 25,
    "G": 25,
    "H": 31,
    "I": 24,
    "J": 22,
    "K": 22,
    "L": 34,
    "M": 25,
    "N": 31,
    "O": 16,
    "P": 31,
    "Q": 20,
    "R": 31,
    "S": 24,
    "T": 24,
    "U": 24,
}

DATETIME_COLUMNS = ("D", "E", "F", "H", "I", "J", "K", "M", "N", "P", "Q", "R")
LIST_VALIDATIONS = {
    "A": '"новый,продленный"',
    "G": '"Да,Нет"',
    "O": '"Да,Нет"',
    "S": '"Да,Нет"',
    "T": '"Да,Нет"',
    "U": '"Да,Нет"',
}


def local_fmt(dt: datetime | None) -> str:
    if not dt:
        return ""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(MOSCOW_TZ).strftime("%d.%m.%Y %H:%M:%S")


def record_data(record: PermitRecord) -> dict:
    try:
        value = json.loads(record.data_json or "{}")
        return value if isinstance(value, dict) else {}
    except Exception:
        return {}


def _field(data: dict, key: str) -> dict:
    value = data.get(key)
    return value if isinstance(value, dict) else {}


def _field_value(data: dict, key: str) -> str:
    return str(_field(data, key).get("field_value", "") or "").strip()


def _field_comment(data: dict, key: str) -> str:
    return str(_field(data, key).get("comment", "") or "").strip()


def _parse_date_value(value: str, *, date_only: bool = False) -> date | datetime | None:
    raw = str(value or "").strip()
    if not raw:
        return None

    formats = (
        "%d.%m.%Y %H:%M:%S",
        "%d.%m.%Y %H:%M",
        "%d.%m.%Y",
    )
    for fmt in formats:
        try:
            parsed = datetime.strptime(raw, fmt)
            return parsed.date() if date_only else parsed
        except ValueError:
            pass

    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        if parsed.tzinfo is not None:
            parsed = parsed.astimezone(MOSCOW_TZ).replace(tzinfo=None)
        return parsed.date() if date_only else parsed
    except ValueError:
        return None


def _max_row(record: PermitRecord) -> list[object | None]:
    """Map the server permit card to the exact A:U MAX import layout.

    Columns without a direct source in the current mobile RPO process are left
    blank intentionally. This matches the reference workbook supplied for import.
    """
    data = record_data(record)
    return [
        "новый",
        _parse_date_value(_field_value(data, "BE"), date_only=True),
        record.permit_number,
        _parse_date_value(_field_value(data, "AT")),
        _parse_date_value(_field_value(data, "AU")),
        _parse_date_value(_field_value(data, "AV")),
        None,
        _parse_date_value(_field_value(data, "AX")),
        _parse_date_value(_field_value(data, "AY")),
        _parse_date_value(_field_value(data, "AZ")),
        _parse_date_value(_field_value(data, "BA")),
        _field_comment(data, "AZ") or None,
        _parse_date_value(_field_value(data, "BC")),
        _parse_date_value(_field_value(data, "BD")),
        None,
        _parse_date_value(_field_value(data, "BF")),
        _parse_date_value(_field_value(data, "BG")),
        _parse_date_value(_field_value(data, "BH")),
        None,
        None,
        None,
    ]


def _style_export_sheet(ws) -> None:
    header_fill = PatternFill("solid", fgColor="1D4ED8")
    header_font = Font(name="Carlito", size=10, bold=True, color="FFFFFF")
    body_font = Font(name="Carlito", size=11)
    neutral_fill = PatternFill("solid", fgColor="F1F5F9")

    ws.row_dimensions[1].height = 96
    for col_letter, width in COLUMN_WIDTHS.items():
        ws.column_dimensions[col_letter].width = width

    for idx, value in enumerate(MAX_HEADERS, start=1):
        cell = ws.cell(row=1, column=idx, value=value)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)

    for row_idx in range(2, MAX_TEMPLATE_LAST_ROW + 1):
        ws.row_dimensions[row_idx].height = 28
        for col_idx in range(1, 22):
            cell = ws.cell(row=row_idx, column=col_idx)
            cell.font = body_font
            cell.alignment = Alignment(vertical="center", wrap_text=True)

        ws[f"B{row_idx}"].fill = neutral_fill
        ws[f"B{row_idx}"].number_format = "dd.mm.yyyy"
        ws[f"C{row_idx}"].number_format = "@"
        for col_letter in DATETIME_COLUMNS:
            ws[f"{col_letter}{row_idx}"].number_format = "dd.mm.yyyy hh:mm"

    table = Table(displayName="MaxUploadTable", ref=f"A1:U{MAX_TEMPLATE_LAST_ROW}")
    table.tableStyleInfo = TableStyleInfo(
        name="TableStyleMedium2",
        showFirstColumn=False,
        showLastColumn=False,
        showRowStripes=True,
        showColumnStripes=False,
    )
    ws.add_table(table)

    for col_letter, formula in LIST_VALIDATIONS.items():
        validation = DataValidation(type="list", formula1=formula, allow_blank=True)
        ws.add_data_validation(validation)
        validation.add(f"{col_letter}2:{col_letter}{MAX_TEMPLATE_LAST_ROW}")

    missing_font = Font(color="991B1B")
    missing_fill = PatternFill("solid", fgColor="FEE2E2")
    required_columns = [col for col in COLUMN_WIDTHS if col != "B"]
    for priority, col_letter in enumerate(required_columns, start=1):
        rule = FormulaRule(
            formula=[f'AND(COUNTA($A2:$U2)>0,{col_letter}2="")'],
            font=missing_font,
            fill=missing_fill,
        )
        ws.conditional_formatting.add(
            f"{col_letter}2:{col_letter}{MAX_TEMPLATE_LAST_ROW}",
            rule,
        )

    invalid_nd_rule = FormulaRule(
        formula=['AND(C2<>"",NOT(OR(LEFT(UPPER(C2),3)="СН-",LEFT(UPPER(C2),3)="CH-")))'],
        font=Font(bold=True, color="92400E"),
        fill=PatternFill("solid", fgColor="FEF3C7"),
    )
    ws.conditional_formatting.add(f"C2:C{MAX_TEMPLATE_LAST_ROW}", invalid_nd_rule)


def _build_instruction_sheet(wb: Workbook) -> None:
    ws = wb.create_sheet("Инструкция")
    for col_letter, width in {
        "A": 29,
        "B": 80,
        "D": 18,
        "E": 18,
        "F": 19,
        "G": 24,
        "H": 24,
    }.items():
        ws.column_dimensions[col_letter].width = width

    ws.merge_cells("A1:H1")
    ws["A1"] = "Шаблон загрузки данных из MAX в Платформу РПО"
    ws.row_dimensions[1].height = 34
    ws["A1"].font = Font(name="Carlito", size=16, bold=True, color="FFFFFF")
    ws["A1"].fill = PatternFill("solid", fgColor="1E3A8A")
    ws["A1"].alignment = Alignment(vertical="center")

    ws.merge_cells("A3:H3")
    ws["A3"] = (
        "Рабочий порядок: заполните лист «Выгрузка РПО» → сохраните файл → "
        "загрузите его в проект → проверьте предварительный просмотр → "
        "нажмите «Внести данные в реестр»."
    )
    ws.row_dimensions[3].height = 44
    ws["A3"].font = Font(name="Carlito", size=11, bold=True, color="1E3A8A")
    ws["A3"].fill = PatternFill("solid", fgColor="DBEAFE")
    ws["A3"].alignment = Alignment(vertical="center", wrap_text=True)

    rules = [
        ("Одна строка — одна запись", "Каждая строка шаблона переносится в отдельную строку реестра РПО."),
        ("Повторяющийся номер НД", "Если один НД указан в нескольких строках, первая подходящая строка обновляет исходную запись, остальные создают дополнительные строки."),
        ("Номер НД", "Заполняйте в формате СН-000000 или CH-000000. Не вставляйте несколько номеров в одну ячейку."),
        ("Признак НД", "Используйте только значения «новый» или «продленный»."),
        ("Продлён до", "Необязательное поле. Заполняется только при наличии даты продления."),
        ("Дата и время", "Используйте формат 14.07.2026 09:44. В одной ячейке должна быть одна дата и одно время."),
        ("Да / Нет", "Для соответствующих полей используйте значения «Да» или «Нет» из выпадающего списка."),
        ("Пустые ячейки", "Красная подсветка означает, что ячейка не заполнена и требует проверки. Столбец «Продлён до» не подсвечивается."),
        ("Заголовки", "Не переименовывайте столбцы, не меняйте порядок A:U и не добавляйте строки выше заголовка."),
        ("Объединение ячеек", "На листе «Выгрузка РПО» объединять ячейки нельзя."),
        ("Сохранение", "Сохраняйте файл в формате .xlsx или .xlsm."),
    ]

    ws["A5"] = "Правило"
    ws["B5"] = "Требование"
    for cell in (ws["A5"], ws["B5"]):
        cell.font = Font(name="Carlito", size=11, bold=True, color="FFFFFF")
        cell.fill = PatternFill("solid", fgColor="2563EB")
        cell.alignment = Alignment(vertical="center")

    for row_idx, (rule_name, requirement) in enumerate(rules, start=6):
        ws[f"A{row_idx}"] = rule_name
        ws[f"B{row_idx}"] = requirement
        ws[f"A{row_idx}"].font = Font(name="Carlito", size=11, bold=True, color="3730A3")
        ws[f"A{row_idx}"].fill = PatternFill("solid", fgColor="E0E7FF")
        ws[f"B{row_idx}"].font = Font(name="Carlito", size=11)
        ws[f"B{row_idx}"].alignment = Alignment(wrap_text=True, vertical="top")
        ws[f"A{row_idx}"].alignment = Alignment(wrap_text=True, vertical="top")

    ws.merge_cells("D5:H5")
    ws["D5"] = "Пример заполнения двух строк по одному НД"
    ws["D5"].font = Font(name="Carlito", size=11, bold=True, color="FFFFFF")
    ws["D5"].fill = PatternFill("solid", fgColor="2563EB")
    ws["D5"].alignment = Alignment(horizontal="center", vertical="center")

    for col, value in zip(("D", "E", "F", "G", "H"), ("Признак НД", "Продлён до", "Номер НД", "Начало работ", "Завершение работ")):
        ws[f"{col}6"] = value
        ws[f"{col}6"].font = Font(name="Carlito", size=11, bold=True, color="FFFFFF")
        ws[f"{col}6"].fill = PatternFill("solid", fgColor="64748B")
        ws[f"{col}6"].alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)

    examples = [
        ("новый", date(2026, 7, 15), "СН-038762", datetime(2026, 7, 14, 9, 44), datetime(2026, 7, 14, 16, 39)),
        ("продленный", date(2026, 7, 16), "СН-038762", datetime(2026, 7, 15, 9, 33), datetime(2026, 7, 15, 16, 38)),
    ]
    for row_idx, row in enumerate(examples, start=7):
        for col_idx, value in enumerate(row, start=4):
            cell = ws.cell(row=row_idx, column=col_idx, value=value)
            cell.font = Font(name="Carlito", size=11)
            cell.alignment = Alignment(vertical="center", wrap_text=True)
        ws[f"E{row_idx}"].number_format = "dd.mm.yyyy"
        ws[f"G{row_idx}"].number_format = "dd.mm.yyyy hh:mm"
        ws[f"H{row_idx}"].number_format = "dd.mm.yyyy hh:mm"

    ws.merge_cells("D10:H10")
    ws["D10"] = "Куда переносится информация"
    ws["D10"].font = Font(name="Carlito", size=11, bold=True, color="FFFFFF")
    ws["D10"].fill = PatternFill("solid", fgColor="1E3A8A")
    ws["D10"].alignment = Alignment(horizontal="center", vertical="center")

    ws["D11"] = "Шаблон MAX"
    ws["E11"] = "Реестр РПО"
    for cell in (ws["D11"], ws["E11"]):
        cell.font = Font(name="Carlito", size=11, bold=True, color="FFFFFF")
        cell.fill = PatternFill("solid", fgColor="64748B")
        cell.alignment = Alignment(horizontal="center", vertical="center")

    mapping_rows = [
        ("A — Признак НД", "B — Признак НД"),
        ("B — Продлён до", "C — Продлён до"),
        ("C — Номер НД", "D — Номер НД"),
        ("D:U — этапы и признаки", "AT:BK — этапы и признаки"),
    ]
    for row_idx, (left, right) in enumerate(mapping_rows, start=12):
        ws[f"D{row_idx}"] = left
        ws[f"E{row_idx}"] = right
        for cell in (ws[f"D{row_idx}"], ws[f"E{row_idx}"]):
            cell.font = Font(name="Carlito", size=11)
            cell.alignment = Alignment(vertical="center", wrap_text=True)


def _build_max_workbook(records: list[PermitRecord]) -> Workbook:
    if len(records) > MAX_TEMPLATE_LAST_ROW - 1:
        raise ValueError(
            f"Шаблон MAX рассчитан максимум на {MAX_TEMPLATE_LAST_ROW - 1} записей за одну выгрузку"
        )

    wb = Workbook()
    ws = wb.active
    ws.title = "Выгрузка РПО"
    _style_export_sheet(ws)

    for row_idx, record in enumerate(records, start=2):
        for col_idx, value in enumerate(_max_row(record), start=1):
            ws.cell(row=row_idx, column=col_idx, value=value)

    _build_instruction_sheet(wb)
    wb.active = 0
    return wb


def build_export(records: list[PermitRecord], export_dir: str, batch_id: int) -> tuple[Path, Path]:
    """Build the MAX-compatible XLSX plus the server audit JSON sidecar."""
    out = Path(export_dir)
    out.mkdir(parents=True, exist_ok=True)

    now_msk = datetime.now(MOSCOW_TZ)
    stamp = now_msk.strftime("%Y%m%d_%H%M%S")
    xlsx_path = out / (
        f"Шаблон_загрузки_данных_MAX_заполненный_"
        f"{now_msk:%d.%m.%Y}_№{batch_id}.xlsx"
    )
    json_path = out / f"RPO_UPDATE_{batch_id}_{stamp}.json"

    wb = _build_max_workbook(records)
    wb.save(xlsx_path)

    stage_keys = [key for key, _ in sorted(STAGES.items(), key=lambda item: item[1]["order"])]
    json_rows = []
    for record in records:
        data = record_data(record)
        normalized_fields = {}
        for key in stage_keys:
            field = _field(data, key)
            if not field:
                continue
            normalized_fields[key] = {
                "label": field.get("stage_label") or STAGES[key]["label"],
                "value": str(field.get("field_value", "") or ""),
                "event_time": field.get("event_time", ""),
                "comment": str(field.get("comment", "") or "").strip(),
                "approval_status": field.get("approval_status", "not_required"),
                "approved_at": field.get("approved_at", ""),
            }

        json_rows.append({
            "record_id": record.id,
            "permit_number": record.permit_number,
            "worker_name": record.worker_name,
            "structural_unit": record.structural_unit or "",
            "device_id": record.device_id,
            "updated_at": record.updated_at.isoformat(),
            "fields": normalized_fields,
        })

    json_path.write_text(
        json.dumps(
            {"version": 4, "batch_id": batch_id, "format": "max-upload", "permits": json_rows},
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return xlsx_path, json_path

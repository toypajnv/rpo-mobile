from __future__ import annotations
from datetime import datetime, timezone
from pathlib import Path
import json
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment
from ..models import MobileEvent


def local_fmt(dt: datetime | None) -> str:
    if not dt:
        return ""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone().strftime("%d.%m.%Y %H:%M:%S")


def build_export(events: list[MobileEvent], export_dir: str, batch_id: int) -> tuple[Path, Path]:
    out = Path(export_dir)
    out.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    xlsx_path = out / f"RPO_UPDATE_{batch_id}_{stamp}.xlsx"
    json_path = out / f"RPO_UPDATE_{batch_id}_{stamp}.json"

    wb = Workbook()
    ws = wb.active
    ws.title = "Изменения РПО"
    headers = ["НД", "Поле", "Этап", "Новое значение", "Работник", "Время события", "Получено сервером", "Комментарий", "ID события"]
    ws.append(headers)
    for cell in ws[1]:
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill("solid", fgColor="0B3A73")
        cell.alignment = Alignment(vertical="center")
    for e in events:
        ws.append([
            e.permit_number, e.field_key, e.stage_label, e.field_value, e.worker_name,
            local_fmt(e.event_time), local_fmt(e.received_at), e.comment, e.id,
        ])
        if e.field_key == "AZ" and e.comment.strip():
            ws.append([
                e.permit_number, "BB", "Причина остановки", e.comment.strip(), e.worker_name,
                local_fmt(e.event_time), local_fmt(e.received_at), "", f"{e.id}:BB",
            ])
    widths = [18, 10, 42, 32, 26, 22, 22, 44, 14]
    for idx, width in enumerate(widths, 1):
        ws.column_dimensions[chr(64 + idx)].width = width
    ws.freeze_panes = "A2"
    wb.save(xlsx_path)

    rows = []
    for e in events:
        rows.append({
            "permit_number": e.permit_number,
            "field_key": e.field_key,
            "stage_label": e.stage_label,
            "value": e.field_value,
            "worker_name": e.worker_name,
            "event_time": e.event_time.isoformat(),
            "received_at": e.received_at.isoformat(),
            "comment": e.comment,
            "event_id": e.id,
        })
        if e.field_key == "AZ" and e.comment.strip():
            rows.append({
                "permit_number": e.permit_number,
                "field_key": "BB",
                "stage_label": "Причина остановки",
                "value": e.comment.strip(),
                "worker_name": e.worker_name,
                "event_time": e.event_time.isoformat(),
                "received_at": e.received_at.isoformat(),
                "comment": "",
                "event_id": f"{e.id}:BB",
            })
    json_path.write_text(json.dumps({"version": 1, "batch_id": batch_id, "changes": rows}, ensure_ascii=False, indent=2), encoding="utf-8")
    return xlsx_path, json_path

from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]

def replace_once(path: str, old: str, new: str) -> None:
    target = ROOT / path
    text = target.read_text(encoding='utf-8')
    if old not in text:
        raise RuntimeError(f'Marker not found in {path}: {old[:120]!r}')
    target.write_text(text.replace(old, new, 1), encoding='utf-8')

old_preview = '''def _preview_record(record: PermitRecord) -> dict:
    data = record_data(record)
    fields = {}
    for key in _dashboard_stage_keys():
        src = data.get(key) or {}
        fields[key] = {
            "label": STAGES[key]["label"],
            "field_value": str(src.get("field_value", "")),
            "comment": str(src.get("comment", "")),
            "event_time": str(src.get("event_time", "")),
        }
    return {
        "id": record.id,
        "permit_number": record.permit_number,
        "worker_name": record.worker_name,
        "updated_at": record.updated_at.isoformat(),
        "previously_exported": bool(record.exported_at),
        "exported_at": record.exported_at.isoformat() if record.exported_at else "",
        "fields": fields,
    }
'''
new_preview = '''def _preview_record(record: PermitRecord) -> dict:
    data = record_data(record)
    fields = {}
    for key in _dashboard_stage_keys():
        src = data.get(key) or {}
        fields[key] = {
            "label": STAGES[key]["label"],
            "field_value": str(src.get("field_value", "")),
            "comment": str(src.get("comment", "")),
            "event_time": str(src.get("event_time", "")),
            "approval_status": str(src.get("approval_status", "not_required")),
        }
    return {
        "id": record.id,
        "permit_number": record.permit_number,
        "worker_name": record.worker_name,
        "structural_unit": record.structural_unit or "",
        "approval": _approval_summary_from_data(data),
        "updated_at": record.updated_at.isoformat(),
        "previously_exported": bool(record.exported_at),
        "exported_at": record.exported_at.isoformat() if record.exported_at else "",
        "fields": fields,
    }
'''
replace_once('server/app/main.py', old_preview, new_preview)

replace_once('server/app/main.py', '        payload.worker_name,\n        payload.permit_number,', '        payload.worker_name,\n        payload.structural_unit or "",\n        payload.permit_number,')
replace_once('server/app/main.py', '''        device_id=payload.device_id,
        worker_name=payload.worker_name,
        permit_number=payload.permit_number,
        field_key=payload.field_key,
        stage_label=payload.stage_label.strip() or STAGES[payload.field_key]["label"],
        event_time=dt_utc(payload.event_time),
        field_value=payload.field_value,
        comment=payload.comment,
    )''', '''        device_id=payload.device_id,
        worker_name=payload.worker_name,
        structural_unit=payload.structural_unit or "",
        permit_number=payload.permit_number,
        field_key=payload.field_key,
        stage_label=payload.stage_label.strip() or STAGES[payload.field_key]["label"],
        event_time=dt_utc(payload.event_time),
        field_value=payload.field_value,
        comment=payload.comment,
        approval_required=payload.field_key != "AZ",
        approval_status="pending" if payload.field_key != "AZ" else "not_required",
    )''')

old_mobile_fields = '''    fields = {
        key: {
            "field_value": str((data.get(key) or {}).get("field_value", "")),
            "event_time": str((data.get(key) or {}).get("event_time", "")),
            "comment": str((data.get(key) or {}).get("comment", "")),
        }
        for key in _dashboard_stage_keys()
        if data.get(key)
    }
    return {
        "permit_number": record.permit_number,
        "worker_name": record.worker_name,
        "updated_at": record.updated_at.isoformat(),
        "fields": fields,
    }'''
new_mobile_fields = '''    fields = {
        key: {
            "field_value": str((data.get(key) or {}).get("field_value", "")),
            "event_time": str((data.get(key) or {}).get("event_time", "")),
            "comment": str((data.get(key) or {}).get("comment", "")),
            "event_id": int((data.get(key) or {}).get("event_id") or 0),
            "approval_required": bool((data.get(key) or {}).get("approval_required")),
            "approval_status": str((data.get(key) or {}).get("approval_status", "not_required")),
            "approved_at": str((data.get(key) or {}).get("approved_at", "")) or None,
        }
        for key in _dashboard_stage_keys()
        if data.get(key)
    }
    return {
        "permit_number": record.permit_number,
        "worker_name": record.worker_name,
        "structural_unit": record.structural_unit or "",
        "approval": _approval_summary_from_data(data),
        "updated_at": record.updated_at.isoformat(),
        "fields": fields,
    }'''
replace_once('server/app/main.py', old_mobile_fields, new_mobile_fields)

replace_once('server/app/main.py', '''        result.append({
            "id": latest.id,
            "worker_name": latest.worker_name,
            "permit_number": latest.permit_number,
            "field_key": "НД",
            "stage_label": f"Наряд-допуск · {len(by_key)} этап(ов)",
            "event_time": latest.event_time,
            "field_value": "\\n".join(values),
            "comment": "\\n".join(comments),
            "received_at": latest.received_at,
            "exported_at": latest.exported_at,
        })''', '''        latest_required = [event for event in by_key.values() if event.approval_required]
        history_approval = (
            "pending" if any(event.approval_status == "pending" for event in latest_required)
            else "approved" if latest_required
            else "not_required"
        )
        approved_times = [event.approved_at for event in latest_required if event.approved_at]
        result.append({
            "id": latest.id,
            "worker_name": latest.worker_name,
            "structural_unit": latest.structural_unit or "",
            "permit_number": latest.permit_number,
            "field_key": "НД",
            "stage_label": f"Наряд-допуск · {len(by_key)} этап(ов)",
            "event_time": latest.event_time,
            "field_value": "\\n".join(values),
            "comment": "\\n".join(comments),
            "approval_required": bool(latest_required),
            "approval_status": history_approval,
            "approved_at": max(approved_times) if approved_times else None,
            "received_at": latest.received_at,
            "exported_at": latest.exported_at,
        })''')

replace_once('server/app/main.py', '    pending = db.scalar(select(func.count()).select_from(PermitRecord).where(PermitRecord.exported_at.is_(None))) or 0\n', '    pending = db.scalar(select(func.count()).select_from(PermitRecord).where(PermitRecord.exported_at.is_(None))) or 0\n    pending_approvals = db.scalar(select(func.count()).select_from(MobileEvent).where(MobileEvent.approval_status == "pending")) or 0\n')
replace_once('server/app/main.py', '''            "worker_name": event.worker_name,
            "permit_number": event.permit_number,
            "field_key": event.field_key,''', '''            "worker_name": event.worker_name,
            "structural_unit": event.structural_unit or "",
            "permit_number": event.permit_number,
            "field_key": event.field_key,''')
replace_once('server/app/main.py', '''            "comment": event.comment,
            "exported_at": event.exported_at,''', '''            "comment": event.comment,
            "approval_required": event.approval_required,
            "approval_status": event.approval_status,
            "approved_at": event.approved_at,
            "exported_at": event.exported_at,''')
replace_once('server/app/main.py', '''        received_today=received_today,
        pending=pending,
        active_workers=active_workers,''', '''        received_today=received_today,
        pending=pending,
        pending_approvals=pending_approvals,
        active_workers=active_workers,''')
replace_once('server/app/main.py', '''        settings_view=settings_view,
        users=users,
    )''', '''        settings_view=settings_view,
        users=users,
        structural_units=STRUCTURAL_UNITS,
    )''')
print('main core v2 part2 applied')

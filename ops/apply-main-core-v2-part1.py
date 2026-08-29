from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]

def replace_once(path: str, old: str, new: str) -> None:
    target = ROOT / path
    text = target.read_text(encoding='utf-8')
    if old not in text:
        raise RuntimeError(f'Marker not found in {path}: {old[:120]!r}')
    target.write_text(text.replace(old, new, 1), encoding='utf-8')

replace_once('server/app/main.py', 'from sqlalchemy import select, func\n', 'from sqlalchemy import select, func, or_\n')
replace_once('server/app/main.py', 'from .database import Base, engine, get_db, SessionLocal\n', 'from .database import Base, engine, get_db, SessionLocal\nfrom .schema_upgrade import ensure_v2_columns\n')
replace_once('server/app/main.py', 'from .schemas import EventCreate, EventOut\n', 'from .schemas import EventCreate, EventOut, STRUCTURAL_UNITS\n')
replace_once('server/app/main.py', 'LATEST_MOBILE_VERSION = "1.1.6"\nMIN_SUPPORTED_MOBILE_VERSION = "1.0.1"\nMOBILE_APK_URL = "https://github.com/toypajnv/rpo-mobile/releases/download/v1.1.6-test/rpo-mobile-1.1.6.apk"', 'LATEST_MOBILE_VERSION = "2.0.0"\nMIN_SUPPORTED_MOBILE_VERSION = "1.0.1"\nMOBILE_APK_URL = "https://github.com/toypajnv/rpo-mobile/releases/download/v2.0.0-test/rpo-mobile-2.0.0.apk"')
replace_once('server/app/main.py', '    Base.metadata.create_all(engine)\n    ensure_admin()', '    Base.metadata.create_all(engine)\n    ensure_v2_columns()\n    ensure_admin()')
replace_once('server/app/main.py', 'app = FastAPI(title=settings.app_name, version="0.4.1", lifespan=lifespan)', 'app = FastAPI(title=settings.app_name, version="0.5.0", lifespan=lifespan)')

old_apply = '''def _apply_event_to_record(db: Session, event: MobileEvent) -> PermitRecord:
    record = db.scalar(select(PermitRecord).where(PermitRecord.permit_number == event.permit_number))
    data = _safe_data(record.data_json if record else None)
    data[event.field_key] = {
        "stage_label": event.stage_label,
        "field_value": event.field_value,
        "event_time": event.event_time.isoformat(),
        "comment": event.comment or "",
        "client_event_id": event.client_event_id,
    }
    if record is None:
        record = PermitRecord(
            permit_number=event.permit_number,
            device_id=event.device_id,
            worker_name=event.worker_name,
            data_json=json.dumps(data, ensure_ascii=False),
            first_received_at=event.received_at or utcnow(),
            updated_at=event.received_at or utcnow(),
        )
        db.add(record)
    else:
        record.device_id = event.device_id
        record.worker_name = event.worker_name
        record.data_json = json.dumps(data, ensure_ascii=False)
        record.updated_at = event.received_at or utcnow()
        record.exported_at = None
        record.export_batch_id = None
    return record
'''
new_apply = '''def _apply_event_to_record(db: Session, event: MobileEvent) -> PermitRecord:
    record = db.scalar(select(PermitRecord).where(PermitRecord.permit_number == event.permit_number))
    data = _safe_data(record.data_json if record else None)
    data[event.field_key] = {
        "stage_label": event.stage_label,
        "field_value": event.field_value,
        "event_time": event.event_time.isoformat(),
        "comment": event.comment or "",
        "client_event_id": event.client_event_id,
        "event_id": event.id,
        "approval_required": bool(event.approval_required),
        "approval_status": event.approval_status or "not_required",
        "approved_at": event.approved_at.isoformat() if event.approved_at else "",
        "approved_by_id": event.approved_by_id,
    }
    if record is None:
        record = PermitRecord(
            permit_number=event.permit_number,
            device_id=event.device_id,
            worker_name=event.worker_name,
            structural_unit=event.structural_unit or "",
            data_json=json.dumps(data, ensure_ascii=False),
            first_received_at=event.received_at or utcnow(),
            updated_at=event.received_at or utcnow(),
        )
        db.add(record)
    else:
        record.device_id = event.device_id
        record.worker_name = event.worker_name
        if event.structural_unit:
            record.structural_unit = event.structural_unit
        record.data_json = json.dumps(data, ensure_ascii=False)
        record.updated_at = event.received_at or utcnow()
        record.exported_at = None
        record.export_batch_id = None
    return record
'''
replace_once('server/app/main.py', old_apply, new_apply)

approval_helpers = '''

def _approval_summary_from_data(data: dict) -> dict:
    required = []
    for key in _dashboard_stage_keys():
        if key == "AZ":
            continue
        field = data.get(key) or {}
        if field and bool(field.get("approval_required")):
            required.append(field)
    pending = [field for field in required if str(field.get("approval_status", "pending")) == "pending"]
    approved = [field for field in required if str(field.get("approval_status", "")) == "approved"]
    approved_times = sorted(
        [str(field.get("approved_at", "")).strip() for field in approved if str(field.get("approved_at", "")).strip()],
        reverse=True,
    )
    if pending:
        status = "pending"
        label = "Ожидает разрешения"
    elif approved:
        status = "approved"
        label = "Работы разрешены"
    else:
        status = "none"
        label = "Разрешений пока нет"
    return {
        "status": status,
        "label": label,
        "pending_count": len(pending),
        "approved_count": len(approved),
        "approved_at": approved_times[0] if approved_times else "",
    }


def _apply_record_filters(stmt, q: str = "", unit: str = ""):
    query = (q or "").strip()
    structural_unit = (unit or "").strip()
    if query:
        pattern = f"%{query}%"
        stmt = stmt.where(or_(
            PermitRecord.permit_number.ilike(pattern),
            PermitRecord.worker_name.ilike(pattern),
            PermitRecord.structural_unit.ilike(pattern),
            PermitRecord.data_json.ilike(pattern),
        ))
    if structural_unit in STRUCTURAL_UNITS:
        stmt = stmt.where(PermitRecord.structural_unit == structural_unit)
    return stmt


def _apply_event_filters(stmt, q: str = "", unit: str = ""):
    query = (q or "").strip()
    structural_unit = (unit or "").strip()
    if query:
        pattern = f"%{query}%"
        stmt = stmt.where(or_(
            MobileEvent.permit_number.ilike(pattern),
            MobileEvent.worker_name.ilike(pattern),
            MobileEvent.structural_unit.ilike(pattern),
            MobileEvent.stage_label.ilike(pattern),
            MobileEvent.field_value.ilike(pattern),
            MobileEvent.comment.ilike(pattern),
        ))
    if structural_unit in STRUCTURAL_UNITS:
        stmt = stmt.where(MobileEvent.structural_unit == structural_unit)
    return stmt
'''
replace_once('server/app/main.py', 'def _record_state(record: PermitRecord) -> tuple[str, str]:\n', approval_helpers + '\n\ndef _record_state(record: PermitRecord) -> tuple[str, str]:\n')

old_work = '''def _work_view(record: PermitRecord) -> dict:
    data = record_data(record)
    visible_keys = _dashboard_stage_keys()
    required_keys = _required_dashboard_stage_keys()
    filled = sum(1 for key in required_keys if _has_stage(data, key))
    total = len(required_keys) or 1
    summary, comments = _record_summary(record)
    status, status_class = _record_state(record)
    stage_items = []
    for key in visible_keys:
        field = data.get(key) or {}
        value = str(field.get("field_value", "")).strip()
        if not value:
            continue
        stage_items.append({
            "key": key,
            "label": STAGES[key]["label"],
            "value": value,
            "comment": str(field.get("comment", "")).strip(),
        })
    return {
        "id": record.id,
        "updated_at": record.updated_at,
        "worker_name": record.worker_name,
        "permit_number": record.permit_number,
        "summary": summary,
        "comments": comments,
        "exported_at": record.exported_at,
        "status": status,
        "status_class": status_class,
        "progress": round(filled * 100 / total),
        "stage_count": filled,
        "stage_total": total,
        "stage_items": stage_items,
    }
'''
new_work = '''def _work_view(record: PermitRecord) -> dict:
    data = record_data(record)
    visible_keys = _dashboard_stage_keys()
    required_keys = _required_dashboard_stage_keys()
    filled = sum(1 for key in required_keys if _has_stage(data, key))
    total = len(required_keys) or 1
    summary, comments = _record_summary(record)
    status, status_class = _record_state(record)
    approval = _approval_summary_from_data(data)
    stage_items = []
    for key in visible_keys:
        field = data.get(key) or {}
        value = str(field.get("field_value", "")).strip()
        if not value:
            continue
        stage_items.append({
            "key": key,
            "label": STAGES[key]["label"],
            "value": value,
            "comment": str(field.get("comment", "")).strip(),
            "event_id": int(field.get("event_id") or 0),
            "approval_required": bool(field.get("approval_required")),
            "approval_status": str(field.get("approval_status", "not_required")),
            "approved_at": str(field.get("approved_at", "")),
        })
    return {
        "id": record.id,
        "updated_at": record.updated_at,
        "worker_name": record.worker_name,
        "structural_unit": record.structural_unit or "",
        "permit_number": record.permit_number,
        "summary": summary,
        "comments": comments,
        "exported_at": record.exported_at,
        "status": status,
        "status_class": status_class,
        "approval": approval,
        "progress": round(filled * 100 / total),
        "stage_count": filled,
        "stage_total": total,
        "stage_items": stage_items,
    }
'''
replace_once('server/app/main.py', old_work, new_work)
print('main core v2 part1 applied')

from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]

def replace_once(path: str, old: str, new: str) -> None:
    target = ROOT / path
    text = target.read_text(encoding="utf-8")
    if old not in text:
        raise RuntimeError(f"Marker not found in {path}: {old[:120]!r}")
    target.write_text(text.replace(old, new, 1), encoding="utf-8")

old_operator_events = '''@app.get("/api/operator/events")
def operator_events(
    request: Request,
    operator: Operator = Depends(current_operator),
    db: Session = Depends(get_db),
    limit: int = Query(100, ge=1, le=500),
):
    records = list(db.scalars(select(PermitRecord).order_by(PermitRecord.updated_at.desc()).limit(limit)))
    result = []
    for record in records:
        item = _work_view(record)
        result.append({
            "id": item["id"],
            "updated_at": item["updated_at"].isoformat(),
            "worker_name": item["worker_name"],
            "permit_number": item["permit_number"],
            "summary": item["summary"],
            "comments": item["comments"],
            "exported": bool(item["exported_at"]),
            "status": item["status"],
            "status_class": item["status_class"],
            "progress": item["progress"],
            "stage_count": item["stage_count"],
            "stage_total": item["stage_total"],
            "stage_items": item["stage_items"],
            "can_delete": is_admin(operator),
        })
    return result
'''
new_operator_events = '''@app.get("/api/operator/events")
def operator_events(
    request: Request,
    operator: Operator = Depends(current_operator),
    db: Session = Depends(get_db),
    limit: int = Query(100, ge=1, le=500),
    q: str = Query(default="", max_length=120),
    unit: str = Query(default="", max_length=80),
):
    stmt = _apply_record_filters(select(PermitRecord), q, unit).order_by(PermitRecord.updated_at.desc()).limit(limit)
    records = list(db.scalars(stmt))
    result = []
    for record in records:
        item = _work_view(record)
        result.append({
            "id": item["id"],
            "updated_at": item["updated_at"].isoformat(),
            "worker_name": item["worker_name"],
            "structural_unit": item["structural_unit"],
            "permit_number": item["permit_number"],
            "summary": item["summary"],
            "comments": item["comments"],
            "exported": bool(item["exported_at"]),
            "status": item["status"],
            "status_class": item["status_class"],
            "approval": item["approval"],
            "progress": item["progress"],
            "stage_count": item["stage_count"],
            "stage_total": item["stage_total"],
            "stage_items": item["stage_items"],
            "can_delete": is_admin(operator),
        })
    return result
'''
replace_once('server/app/main.py', old_operator_events, new_operator_events)

old_transmissions = '''@app.get("/api/operator/transmissions")
def operator_transmissions(
    operator: Operator = Depends(current_operator),
    db: Session = Depends(get_db),
    limit: int = Query(200, ge=1, le=500),
):
    events = list(db.scalars(
        select(MobileEvent)
        .order_by(MobileEvent.received_at.desc(), MobileEvent.id.desc())
        .limit(limit)
    ))
    return [
        {
            "id": event.id,
            "received_at": event.received_at.isoformat(),
            "worker_name": event.worker_name,
            "permit_number": event.permit_number,
            "field_key": event.field_key,
            "stage_label": event.stage_label,
            "field_value": event.field_value,
            "comment": event.comment or "",
            "exported": bool(event.exported_at),
        }
        for event in events
    ]
'''
new_transmissions = '''@app.get("/api/operator/transmissions")
def operator_transmissions(
    operator: Operator = Depends(current_operator),
    db: Session = Depends(get_db),
    limit: int = Query(200, ge=1, le=500),
    q: str = Query(default="", max_length=120),
    unit: str = Query(default="", max_length=80),
):
    stmt = _apply_event_filters(select(MobileEvent), q, unit).order_by(MobileEvent.received_at.desc(), MobileEvent.id.desc()).limit(limit)
    events = list(db.scalars(stmt))
    return [
        {
            "id": event.id,
            "received_at": event.received_at.isoformat(),
            "worker_name": event.worker_name,
            "structural_unit": event.structural_unit or "",
            "permit_number": event.permit_number,
            "field_key": event.field_key,
            "stage_label": event.stage_label,
            "field_value": event.field_value,
            "comment": event.comment or "",
            "approval_required": event.approval_required,
            "approval_status": event.approval_status,
            "approved_at": event.approved_at.isoformat() if event.approved_at else "",
            "exported": bool(event.exported_at),
        }
        for event in events
    ]
'''
replace_once('server/app/main.py', old_transmissions, new_transmissions)

new_routes = '''

@app.post("/api/operator/events/{event_id}/approve")
def approve_mobile_event(
    event_id: int,
    operator: Operator = Depends(current_operator),
    db: Session = Depends(get_db),
):
    event = db.get(MobileEvent, event_id)
    if not event:
        raise HTTPException(status_code=404, detail="Передача не найдена")
    if not event.approval_required or event.field_key == "AZ":
        return {
            "status": "not_required",
            "event_id": event.id,
            "permit_number": event.permit_number,
            "message": "Для остановки работ разрешение оператора не требуется",
        }
    if event.approval_status == "approved":
        return {
            "status": "approved",
            "event_id": event.id,
            "permit_number": event.permit_number,
            "approved_at": event.approved_at.isoformat() if event.approved_at else "",
        }

    approved_at = utcnow()
    event.approval_status = "approved"
    event.approved_at = approved_at
    event.approved_by_id = operator.id

    record = db.scalar(select(PermitRecord).where(PermitRecord.permit_number == event.permit_number))
    if record:
        data = record_data(record)
        current = data.get(event.field_key) if isinstance(data.get(event.field_key), dict) else None
        if current and current.get("client_event_id") == event.client_event_id:
            current["approval_required"] = True
            current["approval_status"] = "approved"
            current["approved_at"] = approved_at.isoformat()
            current["approved_by_id"] = operator.id
            record.data_json = json.dumps(data, ensure_ascii=False)
            record.updated_at = approved_at
    db.commit()
    return {
        "status": "approved",
        "event_id": event.id,
        "permit_number": event.permit_number,
        "field_key": event.field_key,
        "approved_at": approved_at.isoformat(),
        "approved_by": operator.username,
    }


@app.get("/api/operator/analytics")
def operator_analytics(
    operator: Operator = Depends(current_operator),
    db: Session = Depends(get_db),
    q: str = Query(default="", max_length=120),
    unit: str = Query(default="", max_length=80),
):
    now = utcnow()
    records = list(db.scalars(_apply_record_filters(select(PermitRecord), q, unit).order_by(PermitRecord.updated_at.desc())))
    permit_numbers = [record.permit_number for record in records]
    if permit_numbers:
        raw_events = list(db.scalars(
            select(MobileEvent)
            .where(MobileEvent.received_at >= now - timedelta(days=7), MobileEvent.permit_number.in_(permit_numbers))
            .order_by(MobileEvent.received_at.asc())
        ))
    else:
        raw_events = []
    result = _analytics_context(records, raw_events, now)
    result["pending_approvals"] = sum(_approval_summary_from_data(record_data(record))["pending_count"] for record in records)
    return result
'''
replace_once('server/app/main.py', '\n\n@app.delete("/api/operator/permits/{record_id}")', new_routes + '\n\n@app.delete("/api/operator/permits/{record_id}")')

old_export_preview = '''@app.get("/api/operator/export-preview")
def export_preview(
    period_from: str,
    period_to: str,
    operator: Operator = Depends(current_operator),
    db: Session = Depends(get_db),
):
    start, end = _parse_period(period_from, period_to)
    records = list(db.scalars(
        select(PermitRecord)
        .where(PermitRecord.updated_at >= start, PermitRecord.updated_at <= end)
        .order_by(PermitRecord.updated_at.asc())
    ))
    return {
        "records": [_preview_record(record) for record in records],
        "stage_keys": _dashboard_stage_keys(),
        "period_from": start.isoformat(),
        "period_to": end.isoformat(),
    }
'''
new_export_preview = '''@app.get("/api/operator/export-preview")
def export_preview(
    period_from: str,
    period_to: str,
    operator: Operator = Depends(current_operator),
    db: Session = Depends(get_db),
    q: str = Query(default="", max_length=120),
    unit: str = Query(default="", max_length=80),
):
    start, end = _parse_period(period_from, period_to)
    stmt = select(PermitRecord).where(PermitRecord.updated_at >= start, PermitRecord.updated_at <= end)
    stmt = _apply_record_filters(stmt, q, unit).order_by(PermitRecord.updated_at.asc())
    records = list(db.scalars(stmt))
    return {
        "records": [_preview_record(record) for record in records],
        "stage_keys": _dashboard_stage_keys(),
        "period_from": start.isoformat(),
        "period_to": end.isoformat(),
    }
'''
replace_once('server/app/main.py', old_export_preview, new_export_preview)

print("main endpoints v2 applied")

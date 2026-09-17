from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
import hashlib
import json

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from .database import SessionLocal
from .models import MobileEvent, PermitRecord
from .services.exporter import record_data


DEDUPE_WINDOW_SECONDS = 60


def _normalize_text(value: str | None) -> str:
    return " ".join(str(value or "").strip().split())


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _semantic_key(
    permit_number: str,
    worker_name: str,
    structural_unit: str,
    field_key: str,
    field_value: str,
) -> tuple[str, str, str, str, str]:
    return (
        _normalize_text(permit_number).upper(),
        _normalize_text(worker_name).upper(),
        _normalize_text(structural_unit).upper(),
        _normalize_text(field_key).upper(),
        _normalize_text(field_value),
    )


def _payload_semantic_key(payload) -> tuple[str, str, str, str, str]:
    return _semantic_key(
        payload.permit_number,
        payload.worker_name,
        payload.structural_unit or "",
        payload.field_key,
        payload.field_value,
    )


def _event_semantic_key(event: MobileEvent) -> tuple[str, str, str, str, str]:
    return _semantic_key(
        event.permit_number,
        event.worker_name,
        event.structural_unit or "",
        event.field_key,
        event.field_value,
    )


def _lock_id(key: tuple[str, ...]) -> int:
    digest = hashlib.sha256("|".join(key).encode("utf-8")).digest()
    value = int.from_bytes(digest[:8], "big", signed=False)
    return value if value < 2**63 else value - 2**64


def _acquire_semantic_lock(db: Session, payload) -> None:
    """Serialize identical logical submissions on PostgreSQL.

    SQLite is used by the test suite and does not support advisory locks.
    """
    bind = db.get_bind()
    if bind.dialect.name != "postgresql":
        return
    db.execute(
        text("SELECT pg_advisory_xact_lock(:lock_id)"),
        {"lock_id": _lock_id(_payload_semantic_key(payload))},
    )


def _find_recent_semantic_duplicate(
    db: Session,
    payload,
    received_at: datetime,
) -> MobileEvent | None:
    """Return only the latest same stage when it is the same logical press.

    The window is intentionally based on server receipt time, not client event_time:
    two user taps can have different client timestamps while still representing one
    logical notification.
    """
    permit = _normalize_text(payload.permit_number).upper()
    field_key = _normalize_text(payload.field_key).upper()

    latest = db.scalar(
        select(MobileEvent)
        .where(
            func.upper(MobileEvent.permit_number) == permit,
            func.upper(MobileEvent.field_key) == field_key,
        )
        .order_by(MobileEvent.received_at.desc(), MobileEvent.id.desc())
        .limit(1)
    )
    if latest is None:
        return None
    if _event_semantic_key(latest) != _payload_semantic_key(payload):
        return None

    age = received_at - _as_utc(latest.received_at)
    if age < timedelta(0):
        age = timedelta(0)
    if age > timedelta(seconds=DEDUPE_WINDOW_SECONDS):
        return None
    return latest


def _refresh_current_record(db: Session, event: MobileEvent) -> None:
    """Refresh only latest-transmission fields without resetting a decision/export."""
    record = db.scalar(
        select(PermitRecord).where(PermitRecord.permit_number == event.permit_number)
    )
    if record is None:
        return

    data = record_data(record)
    current = data.get(event.field_key)
    if not isinstance(current, dict):
        return
    try:
        current_event_id = int(current.get("event_id") or 0)
    except (TypeError, ValueError):
        current_event_id = 0
    if current_event_id != event.id:
        return

    # Keep approval_status, approved_at, approved_by_id, denied_reason and any
    # future operator metadata already present in the canonical record.
    current["stage_label"] = event.stage_label
    current["field_value"] = event.field_value
    current["event_time"] = event.event_time.isoformat()
    current["comment"] = event.comment or ""

    record.device_id = event.device_id
    record.worker_name = event.worker_name
    if event.structural_unit:
        record.structural_unit = event.structural_unit
    record.data_json = json.dumps(data, ensure_ascii=False)
    record.updated_at = event.received_at


def _current_event_ids(db: Session) -> dict[tuple[str, str], int]:
    current: dict[tuple[str, str], int] = {}
    records = list(db.scalars(select(PermitRecord)))
    for record in records:
        data = record_data(record)
        if not isinstance(data, dict):
            continue
        permit = _normalize_text(record.permit_number).upper()
        for field_key, field in data.items():
            if not isinstance(field, dict):
                continue
            try:
                event_id = int(field.get("event_id") or 0)
            except (TypeError, ValueError):
                event_id = 0
            if event_id:
                current[(permit, str(field_key).upper())] = event_id
    return current


def cleanup_redundant_stage_rows(core) -> int:
    """Remove legacy duplicate rows only inside the server dedupe window.

    The authoritative row is the one already referenced by PermitRecord, which is
    normally the last press. Older identical rows farther than 60 seconds away are
    kept because they may represent a real later repetition of the same stage/value.
    """
    removed = 0
    with SessionLocal() as db:
        current_ids = _current_event_ids(db)
        events = list(
            db.scalars(
                select(MobileEvent).order_by(
                    MobileEvent.received_at.desc(),
                    MobileEvent.id.desc(),
                )
            )
        )
        groups: dict[tuple[str, str, str, str, str], list[MobileEvent]] = {}
        for event in events:
            groups.setdefault(_event_semantic_key(event), []).append(event)

        for (permit, _, _, field_key, _), group in groups.items():
            if len(group) < 2:
                continue
            current_id = current_ids.get((permit, field_key))
            if not current_id:
                continue
            canonical = next((event for event in group if event.id == current_id), None)
            if canonical is None:
                continue

            canonical_received = _as_utc(canonical.received_at)
            duplicates = [
                event
                for event in group
                if event.id != canonical.id
                and timedelta(0)
                <= canonical_received - _as_utc(event.received_at)
                <= timedelta(seconds=DEDUPE_WINDOW_SECONDS)
            ]
            if not duplicates:
                continue

            # Preserve a useful comment if the latest row is blank but an older
            # duplicate contains one. Approval decisions are never reset.
            if not _normalize_text(canonical.comment):
                richer = next(
                    (event for event in duplicates if _normalize_text(event.comment)),
                    None,
                )
                if richer is not None:
                    canonical.comment = richer.comment
                    _refresh_current_record(db, canonical)

            for event in duplicates:
                db.delete(event)
                removed += 1

        if removed:
            db.commit()
    return removed


def install_event_dedupe(core) -> None:
    """Collapse rapid duplicate taps on the server without changing the clients."""
    if getattr(core, "_semantic_event_dedupe_installed", False):
        return
    core._semantic_event_dedupe_installed = True

    original_create = core.create_mobile_event

    def create_mobile_event_deduped(payload, db: Session):
        received_at = core.utcnow()
        _acquire_semantic_lock(db, payload)

        existing = _find_recent_semantic_duplicate(db, payload, received_at)
        if existing is not None:
            # "Last press wins" for transmission metadata. The row id and all
            # operator decision fields stay unchanged, so an approved/denied stage
            # cannot be reset to pending by another identical tap.
            existing.received_at = received_at
            existing.event_time = core.dt_utc(payload.event_time)
            existing.device_id = payload.device_id
            existing.worker_name = payload.worker_name
            existing.structural_unit = payload.structural_unit or ""
            incoming_label = str(payload.stage_label or "").strip()
            if incoming_label:
                existing.stage_label = incoming_label
            existing.field_value = payload.field_value

            incoming_comment = str(payload.comment or "").strip()
            if incoming_comment:
                existing.comment = payload.comment

            _refresh_current_record(db, existing)
            db.commit()
            db.refresh(existing)
            return existing

        # Keep the client's event id. The existing UNIQUE(client_event_id) remains
        # a second idempotency layer for ordinary network retries even after 60 sec.
        return original_create(payload, db)

    core.create_mobile_event = create_mobile_event_deduped
    for route in core.app.routes:
        if (
            getattr(route, "path", None) == "/api/mobile/events"
            and "POST" in (getattr(route, "methods", set()) or set())
        ):
            route.endpoint = create_mobile_event_deduped
            if getattr(route, "dependant", None) is not None:
                route.dependant.call = create_mobile_event_deduped
            break

    # Cleanup is conservative and runs only after the normal core lifespan has
    # created/upgraded tables and rebuilt the canonical permit rows.
    original_lifespan = core.app.router.lifespan_context

    @asynccontextmanager
    async def lifespan_with_duplicate_cleanup(app):
        async with original_lifespan(app) as state:
            cleanup_redundant_stage_rows(core)
            yield state

    core.app.router.lifespan_context = lifespan_with_duplicate_cleanup
    core.cleanup_redundant_stage_rows = lambda: cleanup_redundant_stage_rows(core)

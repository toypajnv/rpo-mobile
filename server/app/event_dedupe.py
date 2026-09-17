from __future__ import annotations

from contextlib import asynccontextmanager
import hashlib
import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from .database import SessionLocal
from .models import MobileEvent, PermitRecord
from .services.exporter import record_data


def _normalize_text(value: str | None) -> str:
    return " ".join(str(value or "").strip().split())


def _semantic_key(permit_number: str, field_key: str, field_value: str) -> tuple[str, str, str]:
    return (
        _normalize_text(permit_number).upper(),
        _normalize_text(field_key).upper(),
        _normalize_text(field_value),
    )


def _semantic_client_event_id(payload) -> str:
    permit, field_key, field_value = _semantic_key(
        payload.permit_number,
        payload.field_key,
        payload.field_value,
    )
    raw = f"{permit}|{field_key}|{field_value}"
    return "semantic-" + hashlib.sha256(raw.encode("utf-8")).hexdigest()[:48]


def _find_semantic_duplicate(db: Session, payload) -> MobileEvent | None:
    permit = _normalize_text(payload.permit_number).upper()
    field_key = _normalize_text(payload.field_key).upper()
    expected_value = _normalize_text(payload.field_value)

    # Query a small recent slice and normalize in Python. This also catches legacy
    # rows that may contain harmless extra whitespace in the transmitted value.
    candidates = list(
        db.scalars(
            select(MobileEvent)
            .where(
                MobileEvent.permit_number == permit,
                MobileEvent.field_key == field_key,
            )
            .order_by(MobileEvent.received_at.desc(), MobileEvent.id.desc())
            .limit(20)
        )
    )
    for event in candidates:
        if _normalize_text(event.field_value) == expected_value:
            return event
    return None


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
    """Remove only non-current duplicate rows left by earlier client retries.

    A row is removed only when the canonical PermitRecord already points to another
    event for the same permit/stage and both rows carry the same transmitted value.
    This keeps the authoritative current event and prevents old pending duplicates
    from being shown in the operator journal.
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
        groups: dict[tuple[str, str, str], list[MobileEvent]] = {}
        for event in events:
            key = _semantic_key(event.permit_number, event.field_key, event.field_value)
            groups.setdefault(key, []).append(event)

        for (permit, field_key, _), group in groups.items():
            if len(group) < 2:
                continue
            current_id = current_ids.get((permit, field_key))
            if not current_id:
                continue
            canonical = next((event for event in group if event.id == current_id), None)
            if canonical is None:
                continue

            # Preserve a useful comment if the current row is blank but an older
            # duplicate contains one. No approval decision is copied or changed.
            if not _normalize_text(canonical.comment):
                richer = next((event for event in group if _normalize_text(event.comment)), None)
                if richer is not None:
                    canonical.comment = richer.comment
                    record = db.scalar(
                        select(PermitRecord).where(PermitRecord.permit_number == canonical.permit_number)
                    )
                    if record is not None:
                        data = record_data(record)
                        current = data.get(canonical.field_key)
                        if isinstance(current, dict) and int(current.get("event_id") or 0) == canonical.id:
                            current["comment"] = canonical.comment or ""
                            record.data_json = json.dumps(data, ensure_ascii=False)

            for event in group:
                if event.id == canonical.id:
                    continue
                db.delete(event)
                removed += 1

        if removed:
            db.commit()
    return removed


def install_event_dedupe(core) -> None:
    """Make a permit stage/value idempotent across Android and iOS retries."""
    if getattr(core, "_semantic_event_dedupe_installed", False):
        return
    core._semantic_event_dedupe_installed = True

    original_create = core.create_mobile_event

    def create_mobile_event_deduped(payload, db: Session):
        existing = _find_semantic_duplicate(db, payload)
        if existing is not None:
            # A changed comment must not create a second stage row. Before an
            # operator decision we allow the comment to be refreshed in-place;
            # after a decision the accepted/denied record remains immutable.
            incoming_comment = str(payload.comment or "").strip()
            current_status = str(existing.approval_status or "not_required")
            if (
                incoming_comment
                and incoming_comment != str(existing.comment or "").strip()
                and current_status in {"pending", "not_required"}
            ):
                existing.comment = incoming_comment
                if str(payload.stage_label or "").strip():
                    existing.stage_label = payload.stage_label
                core._apply_event_to_record(db, existing)
                db.commit()
                db.refresh(existing)
            return existing

        # Use a deterministic server-side id for the same logical stage/value.
        # The existing UNIQUE(client_event_id) constraint then also protects from
        # simultaneous retries that reach the server at the same moment.
        semantic_payload = payload.model_copy(
            update={"client_event_id": _semantic_client_event_id(payload)}
        )
        return original_create(semantic_payload, db)

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

    # Cleanup is intentionally conservative and runs only after the normal core
    # lifespan has created/upgraded tables and rebuilt the canonical permit rows.
    original_lifespan = core.app.router.lifespan_context

    @asynccontextmanager
    async def lifespan_with_duplicate_cleanup(app):
        async with original_lifespan(app) as state:
            cleanup_redundant_stage_rows(core)
            yield state

    core.app.router.lifespan_context = lifespan_with_duplicate_cleanup
    core.cleanup_redundant_stage_rows = lambda: cleanup_redundant_stage_rows(core)

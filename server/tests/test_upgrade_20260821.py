from __future__ import annotations

import json
import unittest
from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import func, select

from app.config import settings
from app.database import Base, SessionLocal, engine
from app.main import (
    DEFAULT_OPERATOR_USERNAME,
    _work_view,
    create_mobile_event,
    delete_permit_record,
    ensure_default_operator,
    mobile_config,
)
from app.models import MobileEvent, Operator, PermitRecord
from app.schemas import EventCreate


class Upgrade20260821Tests(unittest.TestCase):
    def setUp(self) -> None:
        Base.metadata.drop_all(engine)
        Base.metadata.create_all(engine)

    def tearDown(self) -> None:
        Base.metadata.drop_all(engine)

    def test_legacy_payload_without_new_metadata_is_still_accepted(self) -> None:
        payload = EventCreate.model_validate({
            "worker_name": "Иванов И.И.",
            "permit_number": "12345",
            "field_key": "BA",
            "event_time": datetime.now(timezone.utc).isoformat(),
            "field_value": "21.08.2026 10:00",
        })
        self.assertIsNone(payload.client_event_id)
        self.assertEqual(payload.stage_label, "")
        self.assertEqual(payload.comment, "")
        with SessionLocal() as db:
            event = create_mobile_event(payload, db)
            self.assertTrue(event.client_event_id.startswith("legacy-"))
            self.assertEqual(event.stage_label, "Возобновление работ")
            self.assertEqual(event.comment, "")

    def test_optional_replacement_stage_is_visible_but_not_progress_required(self) -> None:
        now = datetime.now(timezone.utc)
        record = PermitRecord(
            permit_number="20001",
            device_id="d1",
            worker_name="Иванов",
            data_json=json.dumps({
                "AT": {"field_value": "1"},
                "RI": {"field_value": "Петров П.П.\tэлектромонтёр"},
            }, ensure_ascii=False),
            first_received_at=now,
            updated_at=now,
        )
        view = _work_view(record)
        self.assertEqual(view["stage_count"], 1)
        self.assertEqual(view["stage_total"], 8)
        self.assertIn("RI", {item["key"] for item in view["stage_items"]})

    def test_operator_account_is_bootstrapped(self) -> None:
        ensure_default_operator()
        with SessionLocal() as db:
            user = db.scalar(select(Operator).where(Operator.username == DEFAULT_OPERATOR_USERNAME))
            self.assertIsNotNone(user)
            self.assertTrue(user.is_active)
            self.assertTrue(user.password_hash.startswith("$argon2"))

    def test_only_admin_can_delete_permit_and_raw_events(self) -> None:
        now = datetime.now(timezone.utc)
        with SessionLocal() as db:
            record = PermitRecord(
                permit_number="30001", device_id="d", worker_name="Иванов",
                data_json="{}", first_received_at=now, updated_at=now,
            )
            db.add(record)
            db.flush()
            db.add(MobileEvent(
                client_event_id="delete-test-event",
                device_id="d", worker_name="Иванов", permit_number="30001",
                field_key="AT", stage_label="Начало подготовки", event_time=now,
                field_value="21.08.2026 10:00", comment="",
            ))
            db.commit()
            record_id = record.id

        with SessionLocal() as db:
            operator = Operator(username="Operator", password_hash="x")
            with self.assertRaises(HTTPException) as ctx:
                delete_permit_record(record_id, operator=operator, db=db)
            self.assertEqual(ctx.exception.status_code, 403)

        with SessionLocal() as db:
            admin = Operator(username=settings.admin_username, password_hash="x")
            result = delete_permit_record(record_id, operator=admin, db=db)
            self.assertEqual(result["status"], "deleted")

        with SessionLocal() as db:
            self.assertEqual(db.scalar(select(func.count()).select_from(PermitRecord)), 0)
            self.assertEqual(db.scalar(select(func.count()).select_from(MobileEvent)), 0)

    def test_mobile_feedback_marks_old_version_supported_not_required(self) -> None:
        cfg = mobile_config("1.0.1")
        self.assertEqual(cfg["latest_app_version"], "1.1.5")
        self.assertTrue(cfg["update_available"])
        self.assertFalse(cfg["update_required"])
        self.assertFalse(cfg["maintenance"])


if __name__ == "__main__":
    unittest.main()

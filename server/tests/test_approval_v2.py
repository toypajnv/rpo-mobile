from __future__ import annotations

import unittest
from datetime import datetime, timezone

from app.database import Base, SessionLocal, engine
from app.main import (
    approve_mobile_event,
    create_mobile_event,
    mobile_permit_lookup,
    operator_analytics,
    operator_events,
    operator_transmissions,
    normalize_no_approval_stages,
)
from app.models import MobileEvent, Operator, PermitRecord
from app.schemas import EventCreate, STRUCTURAL_UNITS


class ApprovalV2Tests(unittest.TestCase):
    def setUp(self) -> None:
        Base.metadata.drop_all(engine)
        Base.metadata.create_all(engine)

    def tearDown(self) -> None:
        Base.metadata.drop_all(engine)

    def _payload(self, key: str = "AT", unit: str = "ЦДПН-1", permit: str = "20000") -> EventCreate:
        return EventCreate(
            client_event_id=f"event-{permit}-{key}-0001",
            device_id="android-test",
            worker_name="Иванов И.И.",
            structural_unit=unit,
            permit_number=permit,
            field_key=key,
            stage_label="Тестовый этап",
            event_time=datetime.now(timezone.utc),
            field_value="29.08.2026 09:00",
            comment="",
        )

    def test_non_stop_event_waits_for_operator_and_approval_updates_mobile_status(self) -> None:
        with SessionLocal() as db:
            event = create_mobile_event(self._payload(), db)
            self.assertTrue(event.approval_required)
            self.assertEqual(event.approval_status, "pending")
            operator = Operator(username="Operator", password_hash="x", is_active=True)
            db.add(operator)
            db.commit()
            result = approve_mobile_event(event.id, operator=operator, db=db)
            self.assertEqual(result["status"], "approved")

        with SessionLocal() as db:
            snapshot = mobile_permit_lookup("20000", db)
            self.assertEqual(snapshot["structural_unit"], "ЦДПН-1")
            self.assertEqual(snapshot["approval"]["status"], "approved")
            self.assertEqual(snapshot["fields"]["AT"]["approval_status"], "approved")

    def test_stop_event_does_not_require_operator_permission(self) -> None:
        with SessionLocal() as db:
            event = create_mobile_event(self._payload(key="AZ", permit="20001"), db)
            self.assertFalse(event.approval_required)
            self.assertEqual(event.approval_status, "not_required")

    def test_finish_and_not_performed_are_information_only(self) -> None:
        with SessionLocal() as db:
            finish = create_mobile_event(self._payload(key="BC", permit="20004"), db)
            not_performed = create_mobile_event(self._payload(key="RN", permit="20005"), db)

            self.assertFalse(finish.approval_required)
            self.assertEqual(finish.approval_status, "not_required")
            self.assertFalse(not_performed.approval_required)
            self.assertEqual(not_performed.approval_status, "not_required")

            finish_snapshot = mobile_permit_lookup("20004", db)
            not_performed_snapshot = mobile_permit_lookup("20005", db)
            self.assertEqual(finish_snapshot["approval"]["status"], "none")
            self.assertEqual(not_performed_snapshot["approval"]["status"], "none")
            self.assertEqual(not_performed_snapshot["fields"]["RN"]["approval_status"], "not_required")

    def test_existing_finish_pending_is_normalized_after_deploy(self) -> None:
        with SessionLocal() as db:
            finish = create_mobile_event(self._payload(key="BC", permit="20006"), db)
            finish.approval_required = True
            finish.approval_status = "pending"
            record = db.scalar(
                __import__("sqlalchemy").select(PermitRecord).where(PermitRecord.permit_number == "20006")
            )
            data = __import__("json").loads(record.data_json)
            data["BC"]["approval_required"] = True
            data["BC"]["approval_status"] = "pending"
            record.data_json = __import__("json").dumps(data, ensure_ascii=False)
            db.commit()

        normalize_no_approval_stages()

        with SessionLocal() as db:
            finish = db.scalar(
                __import__("sqlalchemy").select(MobileEvent).where(MobileEvent.permit_number == "20006")
            )
            record = db.scalar(
                __import__("sqlalchemy").select(PermitRecord).where(PermitRecord.permit_number == "20006")
            )
            data = __import__("json").loads(record.data_json)
            self.assertFalse(finish.approval_required)
            self.assertEqual(finish.approval_status, "not_required")
            self.assertFalse(data["BC"]["approval_required"])
            self.assertEqual(data["BC"]["approval_status"], "not_required")

    def test_structural_units_are_exact_and_filters_work(self) -> None:
        self.assertEqual(STRUCTURAL_UNITS, (
            "ЦДПН-1", "ЦДПН-2", "ЦДПН-3", "ЦДПН-4",
            "ЦППН-1", "ЦППН-2", "ЦСДиТГ", "ЦСиР", "ЦТОиРТ-1", "ЦТОиРТ-2",
        ))
        with SessionLocal() as db:
            create_mobile_event(self._payload(unit="ЦППН-2", permit="20777"), db)
            operator = Operator(username="Operator", password_hash="x", is_active=True)
            db.add(operator)
            db.commit()

            works = operator_events(None, operator=operator, db=db, limit=100, q="Иванов", unit="ЦППН-2")
            transmissions = operator_transmissions(operator=operator, db=db, limit=100, q="20777", unit="ЦППН-2")
            analytics = operator_analytics(operator=operator, db=db, q="Иванов", unit="ЦППН-2")
            self.assertEqual(len(works), 1)
            self.assertEqual(works[0]["structural_unit"], "ЦППН-2")
            self.assertEqual(len(transmissions), 1)
            self.assertEqual(analytics["total"], 1)
            self.assertEqual(analytics["pending_approvals"], 1)

    def test_legacy_client_without_structural_unit_is_still_accepted(self) -> None:
        payload = self._payload(permit="20002").model_copy(update={"structural_unit": None})
        with SessionLocal() as db:
            event = create_mobile_event(payload, db)
            self.assertEqual(event.structural_unit, "")
            self.assertEqual(event.approval_status, "pending")

    def test_resubmitting_same_stage_creates_new_pending_approval(self) -> None:
        with SessionLocal() as db:
            first = create_mobile_event(self._payload(permit="20003"), db)
            operator = Operator(username="Operator", password_hash="x", is_active=True)
            db.add(operator)
            db.commit()
            approve_mobile_event(first.id, operator=operator, db=db)
            second_payload = self._payload(permit="20003").model_copy(update={
                "client_event_id": "event-20003-AT-0002",
                "field_value": "29.08.2026 09:05",
                "event_time": datetime.now(timezone.utc),
            })
            second = create_mobile_event(second_payload, db)
            self.assertNotEqual(first.id, second.id)
            self.assertEqual(second.approval_status, "pending")
            snapshot = mobile_permit_lookup("20003", db)
            self.assertEqual(snapshot["approval"]["status"], "pending")
            self.assertEqual(snapshot["fields"]["AT"]["event_id"], second.id)


if __name__ == "__main__":
    unittest.main()

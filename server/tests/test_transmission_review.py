from __future__ import annotations

import json
import unittest
from datetime import datetime, timedelta, timezone

from app import main
from app.database import Base, SessionLocal, engine
from app.models import Operator, PermitRecord
from app.schemas import EventCreate
from app.services.exporter import record_data
from app.transmission_review import TransmissionReviewRequest


class TransmissionReviewTests(unittest.TestCase):
    def setUp(self) -> None:
        Base.metadata.drop_all(engine)
        Base.metadata.create_all(engine)

    def tearDown(self) -> None:
        Base.metadata.drop_all(engine)

    def _operator(self, db):
        operator = Operator(username="Operator", password_hash="x", is_active=True)
        db.add(operator)
        db.commit()
        return operator

    def test_reject_current_backdated_transmission_restores_previous_stage_value(self) -> None:
        with SessionLocal() as db:
            operator = self._operator(db)
            now = datetime.now(timezone.utc)
            first = main.create_mobile_event(EventCreate(
                client_event_id="review-old-good-1",
                device_id="review-device",
                worker_name="Савочкин А.Н.",
                structural_unit="ЦДПН-2",
                permit_number="СН-040533",
                field_key="AT",
                stage_label="Начало подготовки",
                event_time=now - timedelta(hours=2),
                field_value="04.09.2026 10:13",
                comment="корректная запись",
            ), db)
            second = main.create_mobile_event(EventCreate(
                client_event_id="review-wrong-backdate-2",
                device_id="review-device",
                worker_name="Савочкин А.Н.",
                structural_unit="ЦДПН-2",
                permit_number="СН-040533",
                field_key="AT",
                stage_label="Начало подготовки",
                event_time=now - timedelta(hours=1),
                field_value="03.09.2026 08:00",
                comment="ошибочно отправлено задним числом",
            ), db)

            record = db.query(PermitRecord).filter_by(permit_number="СН-040533").one()
            self.assertEqual(record_data(record)["AT"]["event_id"], second.id)

            result = main.review_transmission(
                second.id,
                TransmissionReviewRequest(decision="rejected", reason="Ошибочная дата"),
                operator=operator,
                db=db,
            )
            self.assertEqual(result["status"], "rejected")
            self.assertEqual(result["restored_event_id"], first.id)
            db.refresh(record)
            restored = record_data(record)["AT"]
            self.assertEqual(restored["event_id"], first.id)
            self.assertEqual(restored["field_value"], "04.09.2026 10:13")
            db.refresh(second)
            self.assertEqual(second.approval_status, "rejected")

    def test_legacy_not_required_transmission_can_be_explicitly_approved(self) -> None:
        with SessionLocal() as db:
            operator = self._operator(db)
            event = main.create_mobile_event(EventCreate(
                client_event_id="review-legacy-1",
                device_id="review-device",
                worker_name="Горбач ИА",
                structural_unit="ЦФМиТ",
                permit_number="09876567",
                field_key="RI",
                stage_label="Замена исполнителей работ",
                event_time=datetime.now(timezone.utc),
                field_value="Одровно Радорлю",
                comment="",
            ), db)
            event.approval_required = False
            event.approval_status = "not_required"
            record = db.query(PermitRecord).filter_by(permit_number="09876567").one()
            data = record_data(record)
            data["RI"]["approval_required"] = False
            data["RI"]["approval_status"] = "not_required"
            record.data_json = json.dumps(data, ensure_ascii=False)
            db.commit()

            result = main.review_transmission(
                event.id,
                TransmissionReviewRequest(decision="approved"),
                operator=operator,
                db=db,
            )
            self.assertEqual(result["status"], "approved")
            db.refresh(event)
            self.assertTrue(event.approval_required)
            self.assertEqual(event.approval_status, "approved")
            db.refresh(record)
            reviewed = record_data(record)["RI"]
            self.assertTrue(reviewed["approval_required"])
            self.assertEqual(reviewed["approval_status"], "approved")

    def test_dashboard_review_asset_has_allow_reject_and_no_global_ban_banner(self) -> None:
        static = main._core.BASE_DIR / "static"
        loader = (static / "dashboard.js").read_text(encoding="utf-8")
        review = (static / "dashboard-transmission-review.js").read_text(encoding="utf-8")
        decisions = (static / "dashboard-decisions.js").read_text(encoding="utf-8")
        self.assertIn("dashboard-transmission-review.js?v=20260904-1", loader)
        self.assertIn("Разрешить", review)
        self.assertIn("Отклонить", review)
        self.assertIn("Не рассмотрено", review)
        self.assertIn("/api/operator/transmissions/${eventId}/review", review)
        self.assertNotIn("rpo-blocked-banner", decisions)


if __name__ == "__main__":
    unittest.main()

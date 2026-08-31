from __future__ import annotations

import unittest
from datetime import datetime, timezone

from fastapi import HTTPException

from app.database import Base, SessionLocal, engine
from app.decision_control import EventDecisionRequest
from app.main import create_mobile_event, decide_mobile_event, mobile_permit_lookup
from app.models import Operator
from app.schemas import EventCreate


class OperatorDecisionControlTests(unittest.TestCase):
    def setUp(self) -> None:
        Base.metadata.drop_all(engine)
        Base.metadata.create_all(engine)

    def tearDown(self) -> None:
        Base.metadata.drop_all(engine)

    def payload(self, permit: str, value: str, client_id: str) -> EventCreate:
        return EventCreate(
            client_event_id=client_id,
            device_id="ios-decision-test",
            worker_name="Иванов И.И.",
            structural_unit="ЦДПН-1",
            permit_number=permit,
            field_key="AT",
            stage_label="Начало подготовки",
            event_time=datetime.now(timezone.utc),
            field_value=value,
            comment="",
        )

    def test_denial_blocks_whole_permit_until_operator_allows_stage(self) -> None:
        with SessionLocal() as db:
            first = create_mobile_event(
                self.payload("DENY-100", "31.08.2026 16:00", "decision-deny-100-0001"), db
            )
            operator = Operator(username="Operator", password_hash="x", is_active=True)
            db.add(operator)
            db.commit()

            denied = decide_mobile_event(
                first.id,
                EventDecisionRequest(decision="denied", reason="Не выполнены меры безопасности"),
                operator=operator,
                db=db,
            )
            self.assertEqual(denied["status"], "denied")
            self.assertTrue(denied["permit_blocked"])

            snapshot = mobile_permit_lookup("DENY-100", db)
            self.assertEqual(snapshot["approval"]["status"], "denied")
            self.assertEqual(snapshot["approval"]["denied_field_key"], "AT")
            self.assertEqual(snapshot["approval"]["denied_stage"], "Начало подготовки")
            self.assertEqual(snapshot["approval"]["denied_reason"], "Не выполнены меры безопасности")
            self.assertEqual(snapshot["fields"]["AT"]["approval_status"], "denied")

            with self.assertRaises(HTTPException) as blocked:
                create_mobile_event(
                    self.payload("DENY-100", "31.08.2026 16:05", "decision-deny-100-0002"), db
                )
            self.assertEqual(blocked.exception.status_code, 422)
            self.assertIn("запрещено оператором", str(blocked.exception.detail))
            self.assertIn("Не выполнены меры безопасности", str(blocked.exception.detail))

            allowed = decide_mobile_event(
                first.id,
                EventDecisionRequest(decision="approved"),
                operator=operator,
                db=db,
            )
            self.assertEqual(allowed["status"], "approved")
            self.assertFalse(allowed["permit_blocked"])

            unblocked = create_mobile_event(
                self.payload("DENY-100", "31.08.2026 16:05", "decision-deny-100-0003"), db
            )
            self.assertEqual(unblocked.approval_status, "pending")
            snapshot = mobile_permit_lookup("DENY-100", db)
            self.assertNotEqual(snapshot["approval"]["status"], "denied")
            self.assertEqual(snapshot["approval"]["denied_count"], 0)

    def test_denial_requires_reason_and_stop_event_cannot_be_denied(self) -> None:
        with SessionLocal() as db:
            first = create_mobile_event(
                self.payload("DENY-101", "31.08.2026 16:00", "decision-deny-101-0001"), db
            )
            operator = Operator(username="Operator", password_hash="x", is_active=True)
            db.add(operator)
            db.commit()

            with self.assertRaises(HTTPException) as missing_reason:
                decide_mobile_event(
                    first.id,
                    EventDecisionRequest(decision="denied", reason=""),
                    operator=operator,
                    db=db,
                )
            self.assertEqual(missing_reason.exception.status_code, 400)

            stop = create_mobile_event(EventCreate(
                client_event_id="decision-stop-101-0001",
                device_id="ios-decision-test",
                worker_name="Иванов И.И.",
                structural_unit="ЦДПН-1",
                permit_number="DENY-102",
                field_key="AZ",
                stage_label="Остановка работ",
                event_time=datetime.now(timezone.utc),
                field_value="31.08.2026 16:10",
                comment="Причина остановки",
            ), db)
            with self.assertRaises(HTTPException) as stop_decision:
                decide_mobile_event(
                    stop.id,
                    EventDecisionRequest(decision="denied", reason="Не требуется"),
                    operator=operator,
                    db=db,
                )
            self.assertEqual(stop_decision.exception.status_code, 400)


if __name__ == "__main__":
    unittest.main()

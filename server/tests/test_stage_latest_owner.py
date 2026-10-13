from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException
from sqlalchemy import func, select

from app import main
from app.database import Base, SessionLocal, engine
from app.models import MobileEvent, Operator, PermitRecord
from app.schemas import EventCreate
from app.services.exporter import record_data
from app.transmission_review import TransmissionReviewRequest
from app.decision_control import EventDecisionRequest


class LatestStageAndOwnershipTests(unittest.TestCase):
    def setUp(self):
        Base.metadata.drop_all(engine)
        Base.metadata.create_all(engine)

    def tearDown(self):
        Base.metadata.drop_all(engine)

    @staticmethod
    def payload(key, value, actor, suffix, stamp, permit="СН-049921"):
        return EventCreate(
            client_event_id=f"stage-current-{suffix}-0001",
            device_id="offline-device",
            worker_name=actor,
            structural_unit="ЦДПН-1",
            permit_number=permit,
            field_key=key,
            stage_label=key,
            event_time=stamp,
            field_value=value,
            comment="",
        )

    def test_latest_value_only_in_operator_list_and_stale_actions_rejected(self):
        now = datetime.now(timezone.utc) - timedelta(minutes=10)
        with SessionLocal() as db:
            operator = Operator(username="Operator",password_hash="x",is_active=True)
            db.add(operator)
            db.commit()

            first = main.create_mobile_event(self.payload("AT", "13.10.2026 09:00", "Иванов И.И.", "a", now), db)
            second = main.create_mobile_event(self.payload("AT", "13.10.2026 09:15", "Иванов И.И.", "b", now + timedelta(minutes=1)), db)
            self.assertNotEqual(first.id, second.id)
            self.assertEqual(db.scalar(select(func.count()).select_from(MobileEvent)), 2)

            events = main.operator_transmissions(operator=operator, db=db, limit=100, q="", unit="")
            self.assertEqual([e["id"] for e in events], [second.id])
            self.assertEqual(events[0]["field_value"], "13.10.2026 09:15")

            dashboard = main._core.dashboard_context(db)
            self.assertEqual([e["id"] for e in dashboard["transmissions"]], [second.id])
            self.assertEqual(dashboard["pending_approvals"], 1)

            with self.assertRaises(HTTPException) as old_approve:
                main.approve_mobile_event(first.id, operator=operator, db=db)
            self.assertEqual(old_approve.exception.status_code, 409)

            with self.assertRaises(HTTPException) as old_decision:
                main.decide_mobile_event(first.id, EventDecisionRequest(decision="approved"), operator=operator, db=db)
            self.assertEqual(old_decision.exception.status_code, 409)

            with self.assertRaises(HTTPException) as old_review:
                main.review_transmission(first.id, TransmissionReviewRequest(decision="approved"), operator=operator, db=db)
            self.assertEqual(old_review.exception.status_code, 409)

            result = main.decide_mobile_event(second.id, EventDecisionRequest(decision="approved"), operator=operator, db=db)
            self.assertEqual(result["status"], "approved")
            self.assertEqual(main.mobile_permit_lookup("СН-049921", db)["fields"]["AT"]["event_id"], second.id)

    def test_different_responsibles_are_saved_per_stage(self):
        now = datetime.now(timezone.utc)-timedelta(minutes=20)
        with SessionLocal() as db:
            first = main.create_mobile_event(self.payload("AT","13.10.2026 08:00","Иванов И.И.","first",now,permit="СН-049922"),db)
            second = main.create_mobile_event(self.payload("AU","13.10.2026 08:45","Петров П.П.","second",now + timedelta(minutes=5),permit="СН-049922"),db)
            snapshot = main.mobile_permit_lookup("СН-049922",db)
            self.assertEqual(snapshot["fields"]["AT"]["worker_name"],"Иванов И.И.")
            self.assertEqual(snapshot["fields"]["AU"]["worker_name"],"Петров П.П.")
            self.assertEqual(snapshot["worker_name"],"Петров П.П.")
            record = db.scalar(select(PermitRecord).where(PermitRecord.permit_number=="СН-049922"))
            data=record_data(record)
            self.assertEqual(data["AT"]["event_id"],first.id)
            self.assertEqual(data["AU"]["event_id"],second.id)

    def test_original_value_is_restored_when_latest_is_rejected(self):
        now = datetime.now(timezone.utc)-timedelta(minutes=10)
        with SessionLocal() as db:
            operator=Operator(username="Operator",password_hash="x",is_active=True)
            db.add(operator)
            db.commit()
            old = main.create_mobile_event(self.payload("AT","13.10.2026 09:00","Иванов И.И.","restore-old",now,permit="СН-049923"),db)
            current = main.create_mobile_event(self.payload("AT","13.10.2026 09:15","Петров П.П.","restore-new",now+timedelta(minutes=1),permit="СН-049923"),db)
            result=main.review_transmission(current.id,TransmissionReviewRequest(decision="rejected",reason="Исправьте время"),operator=operator,db=db)
            self.assertEqual(result["restored_event_id"],old.id)
            snapshot=main.mobile_permit_lookup("СН-049923",db)
            self.assertEqual(snapshot["fields"]["AT"]["worker_name"],"Иванов И.И.")
            self.assertEqual(snapshot["fields"]["AT"]["field_value"],"13.10.2026 09:00")


if __name__=="__main__":
    unittest.main()

from __future__ import annotations

import json
import unittest
from datetime import datetime, timezone

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.config import settings
from app.database import Base, SessionLocal, engine
from app.main import app, create_operator_user
from app.models import MobileEvent, Operator, PermitRecord
from app.security import hash_password


class ManagerReadOnlyRoleTests(unittest.TestCase):
    def setUp(self) -> None:
        Base.metadata.drop_all(engine)
        Base.metadata.create_all(engine)

    def tearDown(self) -> None:
        Base.metadata.drop_all(engine)

    def test_admin_can_create_manager_role(self) -> None:
        with SessionLocal() as db:
            admin = Operator(
                username=settings.admin_username,
                password_hash="x",
                role="operator",
                is_active=True,
            )
            response = create_operator_user(
                username="ChiefViewer",
                password="ChiefViewer123!",
                role="manager",
                operator=admin,
                db=db,
            )
            self.assertEqual(response.status_code, 303)
            created = db.scalar(select(Operator).where(Operator.username == "ChiefViewer"))
            self.assertIsNotNone(created)
            self.assertEqual(created.role, "manager")
            self.assertTrue(created.is_active)

    def test_manager_can_read_and_filter_but_cannot_decide_or_export(self) -> None:
        now = datetime.now(timezone.utc)
        manager_password = "ManagerView123!"
        with SessionLocal() as db:
            manager = Operator(
                username="ManagerViewer",
                password_hash=hash_password(manager_password),
                role="manager",
                is_active=True,
            )
            db.add(manager)
            event = MobileEvent(
                client_event_id="manager-readonly-event-1",
                device_id="manager-test-device",
                worker_name="Иванов И.И.",
                structural_unit="ЦДПН-1",
                permit_number="MGR-100",
                field_key="AT",
                stage_label="Начало подготовки",
                event_time=now,
                field_value="03.09.2026 10:00",
                comment="",
                approval_required=True,
                approval_status="pending",
            )
            db.add(event)
            db.flush()
            record = PermitRecord(
                permit_number="MGR-100",
                device_id="manager-test-device",
                worker_name="Иванов И.И.",
                structural_unit="ЦДПН-1",
                data_json=json.dumps({
                    "AT": {
                        "stage_label": "Начало подготовки",
                        "field_value": "03.09.2026 10:00",
                        "event_time": now.isoformat(),
                        "comment": "",
                        "client_event_id": event.client_event_id,
                        "event_id": event.id,
                        "approval_required": True,
                        "approval_status": "pending",
                    }
                }, ensure_ascii=False),
                first_received_at=now,
                updated_at=now,
            )
            db.add(record)
            db.commit()
            event_id = event.id

        with TestClient(app, base_url="https://testserver") as client:
            login = client.post(
                "/login",
                data={"username": "ManagerViewer", "password": manager_password},
                follow_redirects=False,
            )
            self.assertEqual(login.status_code, 303)

            dashboard = client.get("/dashboard")
            self.assertEqual(dashboard.status_code, 200)
            self.assertIn('data-role="manager"', dashboard.text)
            self.assertIn('Режим «Руководитель»: только просмотр', dashboard.text)
            self.assertIn('body[data-role="manager"] #tab-exports .export-card', dashboard.text)

            works = client.get("/api/operator/events", params={"q": "MGR-100", "unit": "ЦДПН-1"})
            self.assertEqual(works.status_code, 200)
            self.assertEqual(len(works.json()), 1)

            analytics = client.get("/api/operator/analytics", params={"q": "MGR-100", "unit": "ЦДПН-1"})
            self.assertEqual(analytics.status_code, 200)
            self.assertEqual(analytics.json()["total"], 1)

            decision = client.post(
                f"/api/operator/events/{event_id}/decision",
                json={"decision": "approved", "reason": ""},
            )
            self.assertEqual(decision.status_code, 403)
            self.assertIn("только в режиме просмотра", decision.json()["detail"])

            legacy_approve = client.post(f"/api/operator/events/{event_id}/approve")
            self.assertEqual(legacy_approve.status_code, 403)

            export_send = client.post(
                "/exports/send",
                data={
                    "period_from": "2026-09-03T00:00",
                    "period_to": "2026-09-03T23:59",
                    "recipient": "viewer@example.com",
                    "edited_json": "[]",
                },
            )
            self.assertEqual(export_send.status_code, 403)


if __name__ == "__main__":
    unittest.main()

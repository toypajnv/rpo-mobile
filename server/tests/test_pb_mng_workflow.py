import json
import os
import unittest

os.environ["DATABASE_URL"] = "sqlite:////tmp/test_pb_mng.db"
os.environ["MAIL_MODE"] = "file"
os.environ["ADMIN_USERNAME"] = "admin"
os.environ["ADMIN_PASSWORD"] = "Test123!"
os.environ["OUTBOX_DIR"] = "/tmp/pb_mng_outbox"

from fastapi.testclient import TestClient

from app.main import Base, app, engine


class PbMngWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        Base.metadata.drop_all(engine)
        Base.metadata.create_all(engine)

    def headers(self):
        return {"X-PB-Device": "pb-device-test", "X-PB-Token": "pb-secret-test"}

    def test_catalog_and_full_stop_cycle(self):
        with TestClient(app, base_url="https://testserver") as client:
            catalog_response = client.get("/api/pb-mng/catalog")
            self.assertEqual(catalog_response.status_code, 200, catalog_response.text)
            catalog = catalog_response.json()
            self.assertGreaterEqual(len(catalog["violations"]), 170)
            rule = next(item for item in catalog["violations"] if len(item["severities"]) == 1)

            payload = {
                "device_id": "pb-device-test",
                "device_token": "pb-secret-test",
                "initiator": {"name": "Иванов Иван Иванович", "unit": "ЦДПН-1", "pass": "77777С"},
                "occurred_at": "2026-09-25T05:00:00+00:00",
                "block": catalog["blocks"][0],
                "structural_unit": "ЦДПН-1",
                "field": catalog["fields"][0],
                "location": "Куст №123",
                "contractor": "ООО Тест",
                "work_type": catalog["work_types"][0],
                "permit_number": "НД-123",
                "description": "Тестовая остановка без классификации работником",
                "responsible": {"fio": "Петров Петр Петрович", "position": "Мастер", "pass": "12345С"},
            }
            created = client.post(
                "/api/pb-mng/stops",
                data={"payload_json": json.dumps(payload, ensure_ascii=False)},
                files=[("photos", ("before.jpg", b"\xff\xd8\xff\xd9", "image/jpeg"))],
                headers=self.headers(),
            )
            self.assertEqual(created.status_code, 201, created.text)
            stop_id = created.json()["id"]
            self.assertEqual(created.json()["status"], "pending_verification")
            self.assertEqual(created.json()["violation"]["id"], "")
            self.assertEqual(created.json()["severity_label"], "Не классифицировано")

            own = client.get("/api/pb-mng/my-stops", headers=self.headers())
            self.assertEqual(own.status_code, 200, own.text)
            self.assertEqual(own.json()["items"][0]["id"], stop_id)

            login = client.post("/login", data={"username": "admin", "password": "Test123!"}, follow_redirects=False)
            self.assertEqual(login.status_code, 303, login.text)

            reviewed = client.post(
                f"/api/pb-mng/coordinator/stops/{stop_id}/review",
                json={
                    "action": "verify",
                    "note": "Подтверждено",
                    "violation_id": rule["id"],
                    "severity": rule["severities"][0],
                    "severity_context": "",
                    "measures": ["Работы остановлены до устранения", "Внесен в СТОП-ЛИСТ"],
                    "course_name": "",
                    "pkm_required": False,
                    "block_responsible": True,
                    "block_days": None,
                },
            )
            self.assertEqual(reviewed.status_code, 200, reviewed.text)
            self.assertEqual(reviewed.json()["status"], "awaiting_resolution")
            self.assertEqual(reviewed.json()["violation"]["id"], rule["id"])
            self.assertEqual(reviewed.json()["current_severity"], rule["severities"][0])
            self.assertTrue(reviewed.json()["restrictions"])

            registry = client.get("/api/pb-mng/coordinator/stops", params={"q": stop_id, "limit": 1000})
            self.assertEqual(registry.status_code, 200, registry.text)
            self.assertEqual(registry.json()["items"][0]["id"], stop_id)

            coordinator_page = client.get("/pb-mng/coordinator/")
            self.assertEqual(coordinator_page.status_code, 200, coordinator_page.text)
            self.assertIn("Реестр остановок", coordinator_page.text)

            resolution = client.post(
                f"/api/pb-mng/stops/{stop_id}/resolution",
                data={"comment": "Нарушение устранено"},
                files=[("photos", ("after.jpg", b"\xff\xd8\xff\xd9", "image/jpeg"))],
                headers=self.headers(),
            )
            self.assertEqual(resolution.status_code, 200, resolution.text)
            self.assertEqual(resolution.json()["status"], "resolution_submitted")

            accepted = client.post(
                f"/api/pb-mng/coordinator/stops/{stop_id}/resolution-review",
                json={"action": "accept", "note": ""},
            )
            self.assertEqual(accepted.status_code, 200, accepted.text)
            self.assertEqual(accepted.json()["status"], "ready_for_unblock")

            closed = client.post(f"/api/pb-mng/coordinator/stops/{stop_id}/unblock")
            self.assertEqual(closed.status_code, 200, closed.text)
            self.assertEqual(closed.json()["status"], "closed")
            self.assertEqual(closed.json()["restrictions"], [])


if __name__ == "__main__":
    unittest.main()

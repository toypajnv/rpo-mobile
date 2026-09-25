import json
import os

os.environ["DATABASE_URL"] = "sqlite:///./data/test_pb_mng.db"
os.environ["MAIL_MODE"] = "file"
os.environ["ADMIN_USERNAME"] = "admin"
os.environ["ADMIN_PASSWORD"] = "Test123!"

from fastapi.testclient import TestClient

from app.main import Base, app, engine

Base.metadata.drop_all(engine)
Base.metadata.create_all(engine)


def _headers():
    return {"X-PB-Device": "pb-device-test", "X-PB-Token": "pb-secret-test"}


def test_pb_mng_catalog_and_full_stop_cycle():
    with TestClient(app) as client:
        catalog_response = client.get("/api/pb-mng/catalog")
        assert catalog_response.status_code == 200, catalog_response.text
        catalog = catalog_response.json()
        assert len(catalog["violations"]) >= 170
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
            "violation_id": rule["id"],
            "severity": rule["severities"][0],
            "severity_context": "",
            "description": "Тестовая остановка",
            "responsible": {"fio": "Петров Петр Петрович", "position": "Мастер", "pass": "12345С"},
        }
        created = client.post(
            "/api/pb-mng/stops",
            data={"payload_json": json.dumps(payload, ensure_ascii=False)},
            files=[("photos", ("before.jpg", b"\xff\xd8\xff\xd9", "image/jpeg"))],
            headers=_headers(),
        )
        assert created.status_code == 201, created.text
        stop_id = created.json()["id"]
        assert created.json()["status"] == "pending_verification"

        own = client.get("/api/pb-mng/my-stops", headers=_headers())
        assert own.status_code == 200
        assert own.json()["items"][0]["id"] == stop_id

        login = client.post("/login", data={"username": "admin", "password": "Test123!"}, follow_redirects=False)
        assert login.status_code == 303

        reviewed = client.post(
            f"/api/pb-mng/coordinator/stops/{stop_id}/review",
            json={
                "action": "verify",
                "note": "Подтверждено",
                "severity": rule["severities"][0],
                "measures": ["Работы остановлены до устранения", "Внесен в СТОП-ЛИСТ"],
                "course_name": "",
                "pkm_required": False,
                "block_responsible": True,
                "block_days": None,
            },
        )
        assert reviewed.status_code == 200, reviewed.text
        assert reviewed.json()["status"] == "awaiting_resolution"
        assert reviewed.json()["restrictions"]

        resolution = client.post(
            f"/api/pb-mng/stops/{stop_id}/resolution",
            data={"comment": "Нарушение устранено"},
            files=[("photos", ("after.jpg", b"\xff\xd8\xff\xd9", "image/jpeg"))],
            headers=_headers(),
        )
        assert resolution.status_code == 200, resolution.text
        assert resolution.json()["status"] == "resolution_submitted"

        accepted = client.post(
            f"/api/pb-mng/coordinator/stops/{stop_id}/resolution-review",
            json={"action": "accept", "note": ""},
        )
        assert accepted.status_code == 200, accepted.text
        assert accepted.json()["status"] == "ready_for_unblock"

        closed = client.post(f"/api/pb-mng/coordinator/stops/{stop_id}/unblock")
        assert closed.status_code == 200, closed.text
        assert closed.json()["status"] == "closed"
        assert closed.json()["restrictions"] == []

import os
os.environ["DATABASE_URL"] = "sqlite:///./data/test_rpo.db"
os.environ["MAIL_MODE"] = "file"
os.environ["ADMIN_USERNAME"] = "admin"
os.environ["ADMIN_PASSWORD"] = "Test123!"

from fastapi.testclient import TestClient
from app.main import app, Base, engine

Base.metadata.drop_all(engine)
Base.metadata.create_all(engine)


def event_payload(**patch):
    data = {
        "client_event_id": "11111111-1111-1111-1111-111111111111",
        "device_id": "android-test-1",
        "worker_name": "Иванов Иван Иванович",
        "permit_number": "СН-038364",
        "field_key": "AY",
        "stage_label": "Фактическое начало работ",
        "event_time": "2026-08-14T10:30:00+00:00",
        "field_value": "14.08.2026 15:30",
        "comment": "",
    }
    data.update(patch)
    return data


def test_mobile_event_create_and_idempotency():
    with TestClient(app) as c:
        r = c.post("/api/mobile/events", json=event_payload())
        assert r.status_code == 201, r.text
        first = r.json()["id"]
        r2 = c.post("/api/mobile/events", json=event_payload())
        assert r2.status_code == 201
        assert r2.json()["id"] == first


def test_bad_permit_rejected():
    with TestClient(app) as c:
        r = c.post("/api/mobile/events", json=event_payload(client_event_id="22222222-2222-2222-2222-222222222222", permit_number="@@@"))
        assert r.status_code == 422


def test_operator_login():
    with TestClient(app) as c:
        r = c.post("/login", data={"username":"admin","password":"Test123!"}, follow_redirects=False)
        assert r.status_code == 303
        r2 = c.get("/api/operator/events")
        assert r2.status_code == 200

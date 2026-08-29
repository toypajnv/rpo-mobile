from fastapi.testclient import TestClient

from app.main import app


def _payload(client_event_id: str):
    return {
        "client_event_id": client_event_id,
        "device_id": "sync-iteration-device",
        "worker_name": "Иванов Иван Иванович",
        "structural_unit": "ЦДПН-1",
        "permit_number": "НД-ПОДСКАЗКА-2908",
        "field_key": "AT",
        "stage_label": "Начало подготовки",
        "event_time": "2026-08-29T15:00:00+00:00",
        "field_value": "29.08.2026 20:00",
        "comment": "",
    }


def test_identical_stage_with_new_client_id_is_not_duplicated():
    with TestClient(app) as client:
        first = client.post('/api/mobile/events', json=_payload('sync-duplicate-00000001'))
        assert first.status_code == 201, first.text
        second = client.post('/api/mobile/events', json=_payload('sync-duplicate-00000002'))
        assert second.status_code == 201, second.text
        assert second.json()['id'] == first.json()['id']


def test_permit_suggestions_return_previous_server_permits():
    with TestClient(app) as client:
        client.post('/api/mobile/events', json=_payload('sync-suggest-000000001'))
        response = client.get('/api/mobile/permit-suggestions', params={'q': 'ПОДСК'})
        assert response.status_code == 200, response.text
        rows = response.json()
        assert any(row['permit_number'] == 'НД-ПОДСКАЗКА-2908' for row in rows)
        match = next(row for row in rows if row['permit_number'] == 'НД-ПОДСКАЗКА-2908')
        assert match['worker_name'] == 'Иванов Иван Иванович'
        assert match['structural_unit'] == 'ЦДПН-1'

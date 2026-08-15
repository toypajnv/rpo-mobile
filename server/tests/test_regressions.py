from __future__ import annotations

import base64
import json
import tempfile
import unittest
from datetime import datetime, timezone
from email import policy
from email.parser import BytesParser
from pathlib import Path
from unittest.mock import patch

from openpyxl import load_workbook
from sqlalchemy import func, select

from app.config import settings
from app.database import Base, SessionLocal, engine
from app.main import ensure_permit_records, mobile_history
from app.models import MobileEvent, PermitRecord
from app.services.exporter import build_export
from app.services.mailer import send_export


class PermitRegressionTests(unittest.TestCase):
    def setUp(self) -> None:
        Base.metadata.drop_all(engine)
        Base.metadata.create_all(engine)

    def tearDown(self) -> None:
        Base.metadata.drop_all(engine)

    def _event(self, key: str, value: str, client_id: str) -> MobileEvent:
        return MobileEvent(
            client_event_id=client_id,
            device_id="device-test-1",
            worker_name="Иванов И.И.",
            permit_number="34567",
            field_key=key,
            stage_label={
                "AT": "Начало подготовки",
                "AU": "Окончание подготовки",
                "AV": "Передача ОП к ОБПР",
                "AY": "Фактическое начало работ",
                "BC": "Окончание работ",
            }[key],
            event_time=datetime.now(timezone.utc),
            field_value=value,
            comment="",
        )

    def test_backfill_groups_many_events_into_one_permit_row(self) -> None:
        events = [
            self._event("AT", "15.08.2026 11:31", "test-event-at"),
            self._event("AU", "15.08.2026 11:31", "test-event-au"),
            self._event("AV", "15.08.2026 11:32", "test-event-av"),
            self._event("AY", "15.08.2026 11:32", "test-event-ay"),
            self._event("BC", "15.08.2026 11:32", "test-event-bc"),
        ]
        with SessionLocal() as db:
            db.add_all(events)
            db.commit()

        ensure_permit_records()

        with SessionLocal() as db:
            count = db.scalar(select(func.count()).select_from(PermitRecord))
            self.assertEqual(count, 1)
            record = db.scalar(select(PermitRecord).where(PermitRecord.permit_number == "34567"))
            self.assertIsNotNone(record)
            data = json.loads(record.data_json)
            self.assertEqual(set(data), {"AT", "AU", "AV", "AY", "BC"})
            self.assertEqual(data["BC"]["field_value"], "15.08.2026 11:32")

    def test_mobile_history_returns_one_item_per_permit(self) -> None:
        with SessionLocal() as db:
            db.add_all([
                self._event("AT", "15.08.2026 11:31", "history-event-at"),
                self._event("AU", "15.08.2026 11:35", "history-event-au"),
            ])
            db.commit()
            result = mobile_history(device_id="device-test-1", limit=30, db=db)

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["permit_number"], "34567")
        self.assertEqual(result[0]["field_key"], "НД")
        self.assertIn("Начало подготовки", result[0]["field_value"])
        self.assertIn("Окончание подготовки", result[0]["field_value"])

    def _records(self) -> list[PermitRecord]:
        now = datetime.now(timezone.utc)
        return [
            PermitRecord(
                id=1,
                permit_number="34567",
                device_id="device-1",
                worker_name="Иванов И.И.",
                data_json=json.dumps({"AT": {"field_value": "15.08.2026 11:31", "comment": "", "stage_label": "Начало подготовки"}}, ensure_ascii=False),
                first_received_at=now,
                updated_at=now,
            ),
            PermitRecord(
                id=2,
                permit_number="98765",
                device_id="device-2",
                worker_name="Петров П.П.",
                data_json=json.dumps({"AY": {"field_value": "15.08.2026 12:00", "comment": "", "stage_label": "Фактическое начало работ"}}, ensure_ascii=False),
                first_received_at=now,
                updated_at=now,
            ),
        ]

    def test_export_is_one_row_per_permit_and_one_file_email(self) -> None:
        old_mode = settings.mail_mode
        old_outbox = settings.outbox_dir
        try:
            with tempfile.TemporaryDirectory() as tmp:
                export_dir = Path(tmp) / "exports"
                outbox_dir = Path(tmp) / "outbox"
                xlsx_path, json_path = build_export(self._records(), str(export_dir), batch_id=77)

                ws = load_workbook(xlsx_path, read_only=True).active
                self.assertEqual(ws.max_row, 3)  # header + 2 permit rows
                payload = json.loads(json_path.read_text(encoding="utf-8"))
                self.assertEqual(len(payload["permits"]), 2)

                settings.mail_mode = "file"
                settings.outbox_dir = str(outbox_dir)
                send_export(
                    "operator@example.ru",
                    "РПО — тест",
                    "Тест одной выгрузки одним письмом",
                    [xlsx_path, json_path],
                )

                eml_files = list(outbox_dir.glob("*.eml"))
                self.assertEqual(len(eml_files), 1)
                message = BytesParser(policy=policy.default).parsebytes(eml_files[0].read_bytes())
                self.assertEqual(message["To"], "operator@example.ru")
                self.assertEqual(len(list(message.iter_attachments())), 2)
        finally:
            settings.mail_mode = old_mode
            settings.outbox_dir = old_outbox

    def test_resend_api_uses_one_https_request_with_two_attachments(self) -> None:
        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def read(self):
                return b'{"id":"email-test-123"}'

        old_mode = settings.mail_mode
        old_key = settings.resend_api_key
        old_from = settings.resend_from
        old_url = settings.resend_api_url
        try:
            with tempfile.TemporaryDirectory() as tmp:
                xlsx_path, json_path = build_export(self._records(), str(Path(tmp) / "exports"), batch_id=88)
                settings.mail_mode = "resend"
                settings.resend_api_key = "re_test_secret"
                settings.resend_from = "РПО Сервер <rpo@rpo-mng.ru>"
                settings.resend_api_url = "https://api.resend.com/emails"

                with patch("app.services.mailer.urllib_request.urlopen", return_value=FakeResponse()) as mocked:
                    result = send_export(
                        "operator@example.ru",
                        "РПО — выгрузка №88",
                        "Одна выгрузка одним письмом",
                        [xlsx_path, json_path],
                        idempotency_key="rpo-export-88",
                    )

                self.assertEqual(result, "resend:email-test-123")
                self.assertEqual(mocked.call_count, 1)
                req = mocked.call_args.args[0]
                self.assertEqual(req.full_url, "https://api.resend.com/emails")
                headers = {k.lower(): v for k, v in req.header_items()}
                self.assertEqual(headers["authorization"], "Bearer re_test_secret")
                self.assertEqual(headers["idempotency-key"], "rpo-export-88")
                self.assertIn("rpo-server", headers["user-agent"].lower())

                body = json.loads(req.data.decode("utf-8"))
                self.assertEqual(body["from"], "РПО Сервер <rpo@rpo-mng.ru>")
                self.assertEqual(body["to"], ["operator@example.ru"])
                self.assertEqual(len(body["attachments"]), 2)
                filenames = {item["filename"] for item in body["attachments"]}
                self.assertEqual(filenames, {xlsx_path.name, json_path.name})
                for item in body["attachments"]:
                    decoded = base64.b64decode(item["content"])
                    original = xlsx_path if item["filename"] == xlsx_path.name else json_path
                    self.assertEqual(decoded, original.read_bytes())
        finally:
            settings.mail_mode = old_mode
            settings.resend_api_key = old_key
            settings.resend_from = old_from
            settings.resend_api_url = old_url


class DashboardStaticTests(unittest.TestCase):
    def test_preview_ui_contract_and_cache_busting(self) -> None:
        server_dir = Path(__file__).resolve().parents[1]
        template = (server_dir / "app/templates/dashboard.html").read_text(encoding="utf-8")
        script = (server_dir / "app/static/dashboard.js").read_text(encoding="utf-8")

        for element_id in (
            'id="export-form"',
            'id="preview-modal"',
            'id="preview-list"',
            'id="confirm-export-form"',
            'id="confirm-send"',
        ):
            self.assertIn(element_id, template)
        self.assertIn("dashboard.js?v=", template)
        self.assertIn("exportForm?.addEventListener('submit'", script)
        self.assertIn("modal.hidden=false", script.replace(" ", ""))


if __name__ == "__main__":
    unittest.main()

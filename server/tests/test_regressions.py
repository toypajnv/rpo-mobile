from __future__ import annotations

import json
import tempfile
import unittest
from datetime import datetime, timezone
from email import policy
from email.parser import BytesParser
from pathlib import Path

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

    def test_export_is_one_row_per_permit_and_one_email(self) -> None:
        now = datetime.now(timezone.utc)
        records = [
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

        old_mode = settings.mail_mode
        old_outbox = settings.outbox_dir
        try:
            with tempfile.TemporaryDirectory() as tmp:
                export_dir = Path(tmp) / "exports"
                outbox_dir = Path(tmp) / "outbox"
                xlsx_path, json_path = build_export(records, str(export_dir), batch_id=77)

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

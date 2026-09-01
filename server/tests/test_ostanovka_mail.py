from __future__ import annotations

import email.message
import os
import unittest
from unittest.mock import patch

from app import ostanovka_worker as worker


class OstanovkaMailTests(unittest.TestCase):
    def test_sender_filter_can_allow_any_sender(self) -> None:
        self.assertTrue(worker._allowed_sender("one@example.com", "*"))
        self.assertTrue(worker._allowed_sender("two@example.net", ""))
        self.assertTrue(worker._allowed_sender("Registry Bot <trusted@example.com>", "trusted@example.com"))
        self.assertFalse(worker._allowed_sender("other@example.com", "trusted@example.com"))

    def test_subject_and_recipient_filters_are_exact(self) -> None:
        self.assertTrue(worker._allowed_subject("Реестр остановок", "реестр остановок"))
        self.assertFalse(worker._allowed_subject("Реестр остановок 2", "Реестр остановок"))
        self.assertTrue(worker._allowed_recipient(["ostanovka@team.resend.app"], "ostanovka@team.resend.app"))
        self.assertFalse(worker._allowed_recipient(["other@team.resend.app"], "ostanovka@team.resend.app"))

    def test_imap_raw_message_rejects_partial_subject_match(self) -> None:
        message = email.message.EmailMessage()
        message["From"] = "anyone@example.com"
        message["To"] = "ostanovka@rpo-mng.ru"
        message["Subject"] = "Реестр остановок тест"
        message["Message-ID"] = "<partial>"
        message.set_content("test")
        message.add_attachment(b"xlsb", maintype="application", subtype="octet-stream", filename="registry.xlsb")
        with patch.object(worker, "_save_and_import") as importer:
            self.assertFalse(
                worker.process_message(
                    message.as_bytes(),
                    expected_subjects=["Реестр остановок", "Стоп-лист УКЗ"],
                    sender_filter="*",
                )
            )
            importer.assert_not_called()

    def test_imap_raw_message_accepts_any_sender_with_exact_subject(self) -> None:
        message = email.message.EmailMessage()
        message["From"] = "outside@example.net"
        message["To"] = "ostanovka@rpo-mng.ru"
        message["Subject"] = "Реестр остановок"
        message["Message-ID"] = "<exact>"
        message.set_content("test")
        message.add_attachment(b"xlsb", maintype="application", subtype="octet-stream", filename="registry.xlsb")
        with patch.object(worker, "_save_and_import", return_value=True) as importer:
            self.assertTrue(
                worker.process_message(
                    message.as_bytes(),
                    expected_subjects=["Реестр остановок", "Стоп-лист УКЗ"],
                    sender_filter="*",
                )
            )
            importer.assert_called_once()

    def test_ukz_subject_accepts_xlsx_attachment(self) -> None:
        message = email.message.EmailMessage()
        message["From"] = "outside@example.net"
        message["To"] = "ostanovka@rpo-mng.ru"
        message["Subject"] = "Стоп-лист УКЗ"
        message["Message-ID"] = "<ukz>"
        message.set_content("test")
        message.add_attachment(b"xlsx", maintype="application", subtype="vnd.openxmlformats-officedocument.spreadsheetml.sheet", filename="Стоп-лист УКЗ.xlsx")
        with patch.object(worker, "_save_and_import", return_value=True) as importer:
            self.assertTrue(
                worker.process_message(
                    message.as_bytes(),
                    expected_subjects=["Реестр остановок", "Стоп-лист УКЗ"],
                    sender_filter="*",
                )
            )
            self.assertEqual(importer.call_args.kwargs["filename"], "Стоп-лист УКЗ.xlsx")

    def test_one_email_can_contain_one_xlsb_and_one_xlsx(self) -> None:
        message = email.message.EmailMessage()
        message["From"] = "outside@example.net"
        message["To"] = "ostanovka@rpo-mng.ru"
        message["Subject"] = "Реестр остановок"
        message["Message-ID"] = "<both>"
        message.set_content("test")
        message.add_attachment(b"xlsb", maintype="application", subtype="octet-stream", filename="registry.xlsb")
        message.add_attachment(b"xlsx", maintype="application", subtype="octet-stream", filename="Стоп-лист УКЗ.xlsx")
        with patch.object(worker, "_save_and_import", return_value=True) as importer:
            self.assertTrue(worker.process_message(message.as_bytes(), expected_subjects=["Реестр остановок"], sender_filter="*"))
            self.assertEqual(importer.call_count, 2)

    def test_resend_import_stays_disabled_until_required_filters_exist(self) -> None:
        env = {
            "RESEND_API_KEY": "re_test",
            "STOP_RESEND_TO": "ostanovka@team.resend.app",
            "STOP_RESEND_SUBJECT": "",
            "STOP_RESEND_SENDER": "*",
        }
        with patch.dict(os.environ, env, clear=False), patch.object(worker, "_resend_json") as api:
            self.assertEqual(worker.poll_resend_once(), 0)
            api.assert_not_called()

    def test_resend_processes_matching_messages_oldest_first(self) -> None:
        env = {
            "RESEND_API_KEY": "re_test",
            "STOP_RESEND_TO": "ostanovka@team.resend.app",
            "STOP_RESEND_SUBJECT": "Реестр остановок",
            "STOP_RESEND_SENDER": "*",
            "STOP_MAX_ATTACHMENT_MB": "25",
        }
        listing = {
            "data": [
                {
                    "id": "new",
                    "message_id": "<new>",
                    "created_at": "2026-08-31T10:05:00Z",
                    "from": "new@example.net",
                    "to": ["ostanovka@team.resend.app"],
                    "subject": "Реестр остановок",
                    "attachments": [{"filename": "new.xlsb"}],
                },
                {
                    "id": "old",
                    "message_id": "<old>",
                    "created_at": "2026-08-31T10:00:00Z",
                    "from": "old@example.org",
                    "to": ["ostanovka@team.resend.app"],
                    "subject": "Реестр остановок",
                    "attachments": [{"filename": "old.xlsb"}],
                },
            ]
        }

        def fake_api(path: str, *, api_key: str, query=None):
            self.assertEqual(api_key, "re_test")
            if path == "/emails/receiving":
                return listing
            email_id = path.split("/")[3]
            return {"data": [{"filename": f"{email_id}.xlsb", "size": 1024, "download_url": f"https://download.example/{email_id}"}]}

        imported: list[str] = []

        def fake_import(payload: bytes, *, filename: str, message_id: str, sender: str) -> bool:
            imported.append(message_id)
            return True

        with (
            patch.dict(os.environ, env, clear=False),
            patch.object(worker, "_resend_json", side_effect=fake_api),
            patch.object(worker, "_message_imported", return_value=False),
            patch.object(worker, "_download", return_value=b"xlsb"),
            patch.object(worker, "_save_and_import", side_effect=fake_import),
        ):
            self.assertEqual(worker.poll_resend_once(), 2)

        self.assertEqual(imported, ["<old>", "<new>"])


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from app import ostanovka_worker as worker


class OstanovkaMailTests(unittest.TestCase):
    def test_sender_subject_and_recipient_filters_are_exact(self) -> None:
        self.assertTrue(worker._allowed_sender("Registry Bot <trusted@example.com>", "trusted@example.com"))
        self.assertFalse(worker._allowed_sender("other@example.com", "trusted@example.com"))
        self.assertTrue(worker._allowed_subject("Реестр остановок", "реестр остановок"))
        self.assertFalse(worker._allowed_subject("Реестр остановок 2", "Реестр остановок"))
        self.assertTrue(worker._allowed_recipient(["ostanovka@team.resend.app"], "ostanovka@team.resend.app"))
        self.assertFalse(worker._allowed_recipient(["other@team.resend.app"], "ostanovka@team.resend.app"))

    def test_resend_import_stays_disabled_until_all_security_filters_exist(self) -> None:
        env = {
            "RESEND_API_KEY": "re_test",
            "STOP_RESEND_TO": "ostanovka@team.resend.app",
            "STOP_RESEND_SUBJECT": "Реестр остановок",
            "STOP_RESEND_SENDER": "",
        }
        with patch.dict(os.environ, env, clear=False), patch.object(worker, "_resend_json") as api:
            self.assertEqual(worker.poll_resend_once(), 0)
            api.assert_not_called()

    def test_resend_processes_matching_messages_oldest_first(self) -> None:
        env = {
            "RESEND_API_KEY": "re_test",
            "STOP_RESEND_TO": "ostanovka@team.resend.app",
            "STOP_RESEND_SUBJECT": "Реестр остановок",
            "STOP_RESEND_SENDER": "trusted@example.com",
            "STOP_MAX_ATTACHMENT_MB": "25",
        }
        listing = {
            "data": [
                {
                    "id": "new",
                    "message_id": "<new>",
                    "created_at": "2026-08-31T10:05:00Z",
                    "from": "Trusted <trusted@example.com>",
                    "to": ["ostanovka@team.resend.app"],
                    "subject": "Реестр остановок",
                    "attachments": [{"filename": "new.xlsb"}],
                },
                {
                    "id": "old",
                    "message_id": "<old>",
                    "created_at": "2026-08-31T10:00:00Z",
                    "from": "trusted@example.com",
                    "to": ["ostanovka@team.resend.app"],
                    "subject": "Реестр остановок",
                    "attachments": [{"filename": "old.xlsb"}],
                },
                {
                    "id": "ignored",
                    "message_id": "<ignored>",
                    "created_at": "2026-08-31T09:00:00Z",
                    "from": "attacker@example.com",
                    "to": ["ostanovka@team.resend.app"],
                    "subject": "Реестр остановок",
                    "attachments": [{"filename": "bad.xlsb"}],
                },
            ]
        }

        def fake_api(path: str, *, api_key: str, query=None):
            self.assertEqual(api_key, "re_test")
            if path == "/emails/receiving":
                return listing
            email_id = path.split("/")[3]
            return {
                "data": [{
                    "filename": f"{email_id}.xlsb",
                    "size": 1024,
                    "download_url": f"https://download.example/{email_id}",
                }]
            }

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

    def test_already_imported_resend_message_is_skipped_before_download(self) -> None:
        env = {
            "RESEND_API_KEY": "re_test",
            "STOP_RESEND_TO": "ostanovka@team.resend.app",
            "STOP_RESEND_SUBJECT": "Реестр остановок",
            "STOP_RESEND_SENDER": "trusted@example.com",
        }
        listing = {
            "data": [{
                "id": "same",
                "message_id": "<same>",
                "created_at": "2026-08-31T10:00:00Z",
                "from": "trusted@example.com",
                "to": ["ostanovka@team.resend.app"],
                "subject": "Реестр остановок",
                "attachments": [{"filename": "registry.xlsb"}],
            }]
        }
        with (
            patch.dict(os.environ, env, clear=False),
            patch.object(worker, "_resend_json", return_value=listing),
            patch.object(worker, "_message_imported", return_value=True),
            patch.object(worker, "_download") as download,
        ):
            self.assertEqual(worker.poll_resend_once(), 0)
            download.assert_not_called()


if __name__ == "__main__":
    unittest.main()

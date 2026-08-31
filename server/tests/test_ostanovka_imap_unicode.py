from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from app import ostanovka_worker as worker


class _FakeImap:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def login(self, username, password):
        return "OK", [b"logged in"]

    def select(self, folder):
        return "OK", [b"0"]

    def uid(self, command, *args):
        if command == "search":
            # Critical regression check: Cyrillic subject must never be passed to
            # imaplib SEARCH because imaplib encodes command arguments as ASCII.
            assert args == (None, "UNSEEN")
            return "OK", [b""]
        raise AssertionError(f"unexpected UID command: {command} {args}")


class OstanovkaImapUnicodeTests(unittest.TestCase):
    def test_cyrillic_subject_is_validated_after_fetch_not_in_imap_search(self) -> None:
        env = {
            "STOP_IMAP_HOST": "imap.example.test",
            "STOP_IMAP_PORT": "993",
            "STOP_IMAP_USERNAME": "ostanovka@example.test",
            "STOP_IMAP_PASSWORD": "secret",
            "STOP_IMAP_FOLDER": "INBOX",
            "STOP_IMAP_SENDER": "*",
            "STOP_IMAP_SUBJECT": "Реестр остановок",
        }
        with patch.dict(os.environ, env, clear=False), patch.object(worker.imaplib, "IMAP4_SSL", return_value=_FakeImap()):
            self.assertEqual(worker.poll_imap_once(), 0)


if __name__ == "__main__":
    unittest.main()

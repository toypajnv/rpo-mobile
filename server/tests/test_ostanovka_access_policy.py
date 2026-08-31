from __future__ import annotations

from types import SimpleNamespace
import unittest

from app.ostanovka import _apply_access_policy


class OstanovkaAccessPolicyTests(unittest.TestCase):
    def base_result(self) -> dict:
        return {
            "pass_number": "51398",
            "status": "denied",
            "title": "Доступ запрещен",
            "message": "old",
            "requirements": [{"key": "report"}],
        }

    def record(self, access_status: str, stop_reason: str = ""):
        return SimpleNamespace(access_status=access_status, stop_reason=stop_reason)

    def test_empty_access_field_allows_entry(self) -> None:
        result = _apply_access_policy(self.base_result(), self.record(""))
        self.assertEqual(result["status"], "allowed")
        self.assertEqual(result["title"], "Доступ разрешен")
        self.assertEqual(result["requirements"], [])

    def test_explicit_allowed_allows_entry(self) -> None:
        result = _apply_access_policy(self.base_result(), self.record("Разрешен"))
        self.assertEqual(result["status"], "allowed")

    def test_explicit_denied_blocks_and_returns_reason(self) -> None:
        reason = "Нарушение требований безопасного производства работ"
        result = _apply_access_policy(self.base_result(), self.record("Запрещен", reason))
        self.assertEqual(result["status"], "denied")
        self.assertEqual(result["reason"], reason)
        self.assertEqual(result["message"], f"Причина: {reason}")
        self.assertTrue(result["requirements"])

    def test_denied_without_reason_has_clear_message(self) -> None:
        result = _apply_access_policy(self.base_result(), self.record("ЗАПРЕЩЕН", ""))
        self.assertEqual(result["status"], "denied")
        self.assertEqual(result["reason"], "")
        self.assertEqual(result["message"], "Причина запрета в реестре не указана.")


if __name__ == "__main__":
    unittest.main()

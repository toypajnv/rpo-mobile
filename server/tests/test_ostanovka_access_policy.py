from __future__ import annotations

from types import SimpleNamespace
import unittest

from app.ostanovka import _apply_access_policy, _resolve_denial_reason


class FakeDb:
    def __init__(self, scalar_value: str = ""):
        self.scalar_value = scalar_value
        self.scalar_calls = 0

    def scalar(self, statement):
        self.scalar_calls += 1
        return self.scalar_value


class OstanovkaAccessPolicyTests(unittest.TestCase):
    def base_result(self) -> dict:
        return {
            "pass_number": "51398C",
            "status": "denied",
            "title": "Доступ запрещен",
            "message": "old",
            "requirements": [{"key": "report"}],
        }

    def record(self, access_status: str, stop_reason: str = ""):
        return SimpleNamespace(access_status=access_status, stop_reason=stop_reason, pass_number="51398")

    def test_empty_access_field_allows_entry(self) -> None:
        result = _apply_access_policy(self.base_result(), self.record(""))
        self.assertEqual(result["status"], "allowed")
        self.assertEqual(result["title"], "Доступ разрешен")
        self.assertEqual(result["requirements"], [])
        self.assertEqual(result["blocks"], [])

    def test_explicit_allowed_allows_entry(self) -> None:
        result = _apply_access_policy(self.base_result(), self.record("Разрешен"))
        self.assertEqual(result["status"], "allowed")

    def test_explicit_denied_blocks_and_keeps_reason_for_spoiler(self) -> None:
        reason = "Нарушение требований безопасного производства работ"
        result = _apply_access_policy(self.base_result(), self.record("Запрещен", reason))
        self.assertEqual(result["status"], "denied")
        self.assertEqual(result["reason"], reason)
        self.assertEqual(result["message"], "Блокировка по реестру остановок.")
        self.assertTrue(result["requirements"])
        self.assertEqual(result["blocks"][0]["type"], "registry")
        self.assertEqual(result["blocks"][0]["description"], reason)

    def test_denied_without_reason_still_has_registry_block(self) -> None:
        result = _apply_access_policy(self.base_result(), self.record("ЗАПРЕЩЕН", ""))
        self.assertEqual(result["status"], "denied")
        self.assertEqual(result["reason"], "")
        self.assertEqual(result["blocks"][0]["description"], "")

    def test_reason_falls_back_to_latest_non_empty_history_value(self) -> None:
        db = FakeDb("Нарушение требований безопасного производства работ")
        record = self.record("Запрещен", "")
        reason = _resolve_denial_reason(db, record)
        self.assertEqual(reason, "Нарушение требований безопасного производства работ")
        self.assertEqual(db.scalar_calls, 1)

        result = _apply_access_policy(self.base_result(), record, reason_override=reason)
        self.assertEqual(result["reason"], reason)
        self.assertEqual(result["blocks"][0]["description"], reason)

    def test_current_reason_wins_without_history_query(self) -> None:
        db = FakeDb("Старая причина")
        record = self.record("Запрещен", "Актуальная причина")
        reason = _resolve_denial_reason(db, record)
        self.assertEqual(reason, "Актуальная причина")
        self.assertEqual(db.scalar_calls, 0)


if __name__ == "__main__":
    unittest.main()

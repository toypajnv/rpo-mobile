from __future__ import annotations

import unittest

from fastapi.testclient import TestClient

from app.database import Base, SessionLocal, engine
from app.main import app
from app.stop_registry import (
    StopRegistryImport,
    StopRegistryRecord,
    lookup_pass,
    normalize_pass_number,
)


class StopRegistryTests(unittest.TestCase):
    def setUp(self) -> None:
        Base.metadata.drop_all(engine)
        Base.metadata.create_all(engine)

    def tearDown(self) -> None:
        Base.metadata.drop_all(engine)

    def _record(
        self,
        pass_number: str,
        *,
        date: str,
        row: int,
        access: str,
        report: str = "ДА",
        course: str = "ДА",
        pkm: str = "ДА",
        course_name: str = "",
    ) -> StopRegistryRecord:
        return StopRegistryRecord(
            pass_number=pass_number,
            pass_raw=pass_number,
            record_date=date,
            fio="Иванов Иван Иванович",
            company="Тестовая организация",
            stop_reason="Тестовая причина",
            measures="Тестовое мероприятие",
            report_status=report,
            course_name=course_name,
            course_status=course,
            pkm_status=pkm,
            access_status=access,
            source_row=row,
        )

    def _mark_registry_ready(self) -> None:
        with SessionLocal() as db:
            db.add(
                StopRegistryImport(
                    file_hash="a" * 64,
                    file_name="registry.xlsb",
                    source_rows=1,
                    indexed_rows=1,
                    unique_passes=1,
                )
            )
            db.commit()

    def test_pass_number_normalization_handles_labels_hyphens_and_cyrillic_lookalikes(self) -> None:
        self.assertEqual(normalize_pass_number("Пропуск № 51398"), "51398")
        self.assertEqual(normalize_pass_number(" 12-34С "), "12-34C")
        self.assertEqual(normalize_pass_number("51234 А"), "51234A")
        self.assertEqual(normalize_pass_number("%%%%"), "")

    def test_latest_allowed_row_overrides_older_denied_history(self) -> None:
        with SessionLocal() as db:
            db.add(self._record("51398", date="2026-07-01", row=100, access="ЗАПРЕЩЕН", report="НЕТ"))
            db.add(self._record("51398", date="2026-08-20", row=200, access="РАЗРЕШЕН"))
            db.commit()

            result = lookup_pass(db, "51398")
            self.assertEqual(result["status"], "allowed")
            self.assertEqual(result["requirements"], [])

    def test_later_sheet_row_wins_when_dates_are_equal(self) -> None:
        with SessionLocal() as db:
            db.add(self._record("37924", date="2026-08-20", row=100, access="ЗАПРЕЩЕН"))
            db.add(self._record("37924", date="2026-08-20", row=101, access="РАЗРЕШЕН"))
            db.commit()

            result = lookup_pass(db, "37924")
            self.assertEqual(result["status"], "allowed")

    def test_latest_denied_row_explains_report_course_and_pkm(self) -> None:
        with SessionLocal() as db:
            db.add(
                self._record(
                    "77777",
                    date="2026-08-30",
                    row=300,
                    access="ЗАПРЕЩЕН",
                    report="НЕТ",
                    course="НЕТ",
                    pkm="НЕТ",
                    course_name="Безопасное производство работ",
                )
            )
            db.commit()

            result = lookup_pass(db, "77777")
            self.assertEqual(result["status"], "denied")
            requirements = {item["key"]: item for item in result["requirements"]}
            self.assertEqual(requirements["report"]["state"], "required")
            self.assertIn("Необходимо предоставить", requirements["report"]["value"])
            self.assertEqual(requirements["course"]["state"], "required")
            self.assertIn("Безопасное производство работ", requirements["course"]["value"])
            self.assertEqual(requirements["pkm"]["state"], "required")

    def test_blank_latest_access_fails_closed_instead_of_granting_access(self) -> None:
        with SessionLocal() as db:
            db.add(self._record("88888", date="2026-08-30", row=400, access="", report="НЕТ"))
            db.commit()

            result = lookup_pass(db, "88888")
            self.assertEqual(result["status"], "denied")
            self.assertIn("Статус допуска не определен", result["message"])

    def test_pass_absent_from_loaded_stop_registry_is_allowed(self) -> None:
        with SessionLocal() as db:
            result = lookup_pass(db, "99999")
            self.assertEqual(result["status"], "allowed")
            self.assertIn("отсутствует", result["message"])

    def test_public_api_is_unavailable_until_first_registry_import(self) -> None:
        with TestClient(app) as client:
            response = client.post("/api/ostanovka/check", json={"pass_number": "51398"})
            self.assertEqual(response.status_code, 503)
            self.assertIn("еще не загружен", response.json()["detail"])

    def test_public_api_returns_only_access_information_not_personal_data(self) -> None:
        self._mark_registry_ready()
        with SessionLocal() as db:
            db.add(self._record("51398", date="2026-08-30", row=500, access="ЗАПРЕЩЕН", report="НЕТ"))
            db.commit()

        with TestClient(app) as client:
            response = client.post("/api/ostanovka/check", json={"pass_number": "51398"})
            self.assertEqual(response.status_code, 200)
            payload = response.json()
            self.assertEqual(payload["status"], "denied")
            self.assertNotIn("fio", payload)
            self.assertNotIn("company", payload)
            self.assertNotIn("stop_reason", payload)
            self.assertNotIn("Иванов", response.text)

    def test_public_page_is_noindex_and_not_cached(self) -> None:
        with TestClient(app) as client:
            response = client.get("/ostanovka/")
            self.assertEqual(response.status_code, 200)
            self.assertIn("Проверка допуска", response.text)
            self.assertEqual(response.headers.get("x-robots-tag"), "noindex, nofollow")
            self.assertEqual(response.headers.get("cache-control"), "no-store")


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import unittest

from fastapi.testclient import TestClient

from app.database import Base, SessionLocal, engine
from app.main import app
from app.stop_registry import StopRegistryImport, StopRegistryRecord
from app.ukz_registry import UkzBlockImport, UkzBlockRecord


class OstanovkaUkzIntegrationTests(unittest.TestCase):
    def setUp(self) -> None:
        Base.metadata.drop_all(engine)
        Base.metadata.create_all(engine)
        with SessionLocal() as db:
            db.add(StopRegistryImport(file_hash="a" * 64, file_name="registry.xlsb", source_rows=1, indexed_rows=1, unique_passes=1))
            db.commit()

    def tearDown(self) -> None:
        Base.metadata.drop_all(engine)

    def _stop_record(self, *, fio: str, access: str = "") -> StopRegistryRecord:
        return StopRegistryRecord(
            pass_number="51398", pass_raw="51398", record_date="2026-08-31", fio=fio, company="Тест",
            stop_reason="Нарушение из основного реестра", measures="", report_status="ДА", course_name="",
            course_status="ДА", pkm_status="ДА", access_status=access, source_row=100,
        )

    def _mark_ukz_ready(self) -> None:
        with SessionLocal() as db:
            db.add(UkzBlockImport(file_hash="b" * 64, file_name="Стоп-лист УКЗ.xlsx", source_rows=1, indexed_rows=1))
            db.commit()

    def test_missing_c_suffix_is_added_and_legacy_numeric_record_is_found(self) -> None:
        with SessionLocal() as db:
            db.add(self._stop_record(fio="Иванов Иван Иванович", access="")); db.commit()
        with TestClient(app) as client:
            payload = client.post("/api/ostanovka/check", json={"pass_number": "51398"}).json()
        self.assertEqual(payload["pass_number"], "51398C")
        self.assertEqual(payload["status"], "allowed")

    def test_video_analytics_block_has_no_public_violation_description(self) -> None:
        with SessionLocal() as db:
            db.add(self._stop_record(fio="Иванов И.И.", access="")); db.commit()
        self._mark_ukz_ready()
        with SessionLocal() as db:
            db.add(UkzBlockRecord(
                fio_raw="Иванов Иван Иванович", fio_normalized="ИВАНОВ ИВАН ИВАНОВИЧ", surname="ИВАНОВ",
                first_name="ИВАН", patronymic="ИВАНОВИЧ", block_kind="video", marker_text="БДД",
                violation_description="Выход в опасную зону", source_sheet="Стоп-лист", source_row=2,
            )); db.commit()
        with TestClient(app) as client:
            response = client.post("/api/ostanovka/check", json={"pass_number": "51398С"})
            payload = response.json()
        self.assertEqual(payload["status"], "denied")
        self.assertEqual(payload["blocks"][0]["title"], "Блокировка по видеоаналитике")
        self.assertEqual(payload["blocks"][0]["description"], "")
        self.assertNotIn("Выход в опасную зону", response.text)

    def test_corporate_block_mentions_corporate_protection_only_once(self) -> None:
        with SessionLocal() as db:
            record = self._stop_record(fio="Петров Петр Петрович", access="Разрешен")
            record.pass_number = "60000"; db.add(record); db.commit()
        self._mark_ukz_ready()
        with SessionLocal() as db:
            db.add(UkzBlockRecord(
                fio_raw="Петров Петр Петрович", fio_normalized="ПЕТРОВ ПЕТР ПЕТРОВИЧ", surname="ПЕТРОВ",
                first_name="ПЕТР", patronymic="ПЕТРОВИЧ", block_kind="corporate", marker_text="УКЗ",
                violation_description="Нарушение пропускного режима", source_sheet="Стоп-лист", source_row=3,
            )); db.commit()
        with TestClient(app) as client:
            response = client.post("/api/ostanovka/check", json={"pass_number": "60000"})
            payload = response.json()
        self.assertEqual(payload["status"], "denied")
        self.assertEqual(payload["message"], "")
        self.assertEqual(payload["blocks"][0]["title"], "Пропуск заблокирован")
        self.assertEqual(payload["blocks"][0]["message"], "Обратитесь в Блок корпоративной защиты")
        self.assertEqual(payload["blocks"][0]["description"], "")
        self.assertNotIn("Нарушение пропускного режима", response.text)
        self.assertEqual(response.text.count("Блок корпоративной защиты"), 1)

    def test_registry_block_exposes_stop_reason_for_spoiler(self) -> None:
        with SessionLocal() as db:
            db.add(self._stop_record(fio="Сидоров Сидор Сидорович", access="Запрещен")); db.commit()
        with TestClient(app) as client:
            payload = client.post("/api/ostanovka/check", json={"pass_number": "51398"}).json()
        self.assertEqual(payload["blocks"][0]["type"], "registry")
        self.assertEqual(payload["blocks"][0]["description"], "Нарушение из основного реестра")

    def test_public_page_spoiler_is_registry_only(self) -> None:
        with TestClient(app) as client:
            response = client.get("/ostanovka/")
        self.assertIn("item.type==='registry' && item.description", response.text)
        self.assertIn("Показать причину приостановки", response.text)

    def test_wrong_letter_suffix_is_rejected(self) -> None:
        with TestClient(app) as client:
            response = client.post("/api/ostanovka/check", json={"pass_number": "51398A"})
        self.assertEqual(response.status_code, 400)
        self.assertIn("заканчиваться", response.json()["detail"])


if __name__ == "__main__":
    unittest.main()

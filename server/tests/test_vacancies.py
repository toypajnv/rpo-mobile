"""Regression coverage for vacancy monitor filters, validation and hourly scan."""
from __future__ import annotations

import unittest
import io
import re
from unittest.mock import MagicMock
from urllib.request import Request as UrlRequest
from urllib.parse import unquote
import os
from datetime import datetime, timezone
from unittest.mock import patch

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app import vacancies


class TestVacancyFilters(unittest.TestCase):
    def test_company_group_detection(self):
        expected = {
            "АО СИБУР": "СИБУР",
            "АО Транснефть-Сибирь": "Транснефть",
            "ПАО НОВАТЭК": "НОВАТЭК",
            "ООО Газпром нефть": "Газпром",
            "АО Самотлорнефтегаз": "Роснефть",
            "ООО РН-Уватнефтегаз": "Роснефть",
        }
        for company, brand in expected.items():
            self.assertEqual(vacancies.company_brand(company), brand)
        self.assertIsNone(vacancies.company_brand("Сервисная компания Нефтегаз"))

    def test_titles(self):
        for title in (
            "Ведущий специалист по охране труда",
            "Главный специалист по промышленной безопасности",
            "Специалист по ПБОТОС",
            "Инженер по пожарной безопасности",
            "HSE Manager",
            "Инженер-эколог",
            "Начальник отдела ПЭБ",
        ):
            self.assertTrue(vacancies.relevant_title(title), title)
        for title in (
            "Специалист информационной безопасности",
            "Начальник службы безопасности",
            "Охранник",
            "Программист Python",
        ):
            self.assertFalse(vacancies.relevant_title(title), title)

    def test_city_and_source_is_strict(self):
        item = {
            "id": "1234567",
            "name": "Специалист по охране труда",
            "employer": {"name": "Транснефть-Сибирь"},
            "area": {"name": "Тюмень"},
            "published_at": "2026-10-28T12:00:00+0500",
            "salary": {"from": 150000, "to": 200000, "currency": "RUR"},
        }
        result = vacancies.parse_vacancy(item, "Тюмень")
        self.assertEqual(result["brand"], "Транснефть")
        self.assertEqual(result["url"], "https://hh.ru/vacancy/1234567")
        self.assertEqual(result["salary"], "150 000–200 000 ₽")
        self.assertEqual(result["published_at"].tzinfo, timezone.utc)
        self.assertIsNone(vacancies.parse_vacancy(item, "Нижневартовск"))
        self.assertIsNone(vacancies.parse_vacancy({**item, "id": "not-number"}, "Тюмень"))

    def test_headhunter_uses_urllib_request_not_fastapi_request(self):
        class FakeResponse:
            def __enter__(self):
                return io.BytesIO(b'{"items":[],"pages":0}')
            def __exit__(self, *_):
                pass
        with patch("app.vacancies.urlopen", return_value=FakeResponse()) as open_mock:
            result = vacancies.hh_json("/vacancies", {"text": "охрана труда"})
        self.assertEqual(result["items"], [])
        request = open_mock.call_args.args[0]
        self.assertIsInstance(request, UrlRequest)
        self.assertIn("охрана", unquote(request.full_url))
        self.assertEqual(request.get_header("Accept"), "application/json")
    def test_source_errors_never_bypass_captcha(self):
        with patch.object(vacancies, "hh_json", side_effect=RuntimeError("HTTP 403")):
            with self.assertRaisesRegex(RuntimeError, "403"):
                vacancies.fetch_current_vacancies()

    def test_query_filters_and_new(self):
        engine = create_engine("sqlite://")
        vacancies.TrackedVacancy.__table__.create(engine)
        vacancies.VacancySourceSetting.__table__.create(engine)
        current = datetime.now(timezone.utc)
        with Session(engine) as db:
            db.add_all([
                vacancies.TrackedVacancy(
                    source="hh.ru", source_id="1", brand="СИБУР", employer="СИБУР",
                    title="Специалист по ОТ", city="Тюмень", url="https://hh.ru/vacancy/1",
                    published_at=current, first_seen_at=current, last_seen_at=current, active=True,
                ),
                vacancies.TrackedVacancy(
                    source="hh.ru", source_id="2", brand="Роснефть", employer="РН-Уватнефтегаз",
                    title="Инженер по ПБ", city="Нижневартовск", url="https://hh.ru/vacancy/2",
                    published_at=current, first_seen_at=current, last_seen_at=current, active=True,
                ),
                vacancies.TrackedVacancy(
                    source="hh.ru", source_id="3", brand="СИБУР", employer="СИБУР",
                    title="Инженер по ОТ", city="Тюмень", url="https://hh.ru/vacancy/3",
                    published_at=current, first_seen_at=current, last_seen_at=current, active=False,
                ),
            ])
            db.commit()
            results, count = vacancies.query_vacancies(db, brand="СИБУР", city="Тюмень")
            self.assertEqual(count, 1)
            self.assertEqual(results[0].source_id, "1")
            results, count = vacancies.query_vacancies(db, text="Уват")
            self.assertEqual(count, 1)
            self.assertEqual(results[0].source_id, "2")
            results, count = vacancies.query_vacancies(db, fresh=True)
            self.assertEqual(count, 2)


    def test_page_requires_separate_vacancy_login(self):
        from fastapi.testclient import TestClient
        from app.main import app
        from app.security import hash_password
        with patch.dict(os.environ, {"VACANCY_ADMIN_PASSWORD_HASH": hash_password("DummyTestPass!2026") }):
            with TestClient(app, base_url="https://testserver") as client:
                response = client.get("/vacancies", follow_redirects=False)
                self.assertEqual(response.status_code, 303)
                self.assertEqual(response.headers.get("location"), "/vacancies/login")
                bad = client.post("/vacancies/login", data={"username": "admin", "password": "wrong"})
                self.assertEqual(bad.status_code, 400)
                self.assertIn("Неверный", bad.text)
                logged = client.post(
                    "/vacancies/login", data={"username": "admin", "password": "DummyTestPass!2026"},
                    follow_redirects=False,
                )
                self.assertEqual(logged.status_code, 303)
                page = client.get("/vacancies")
                self.assertEqual(page.status_code, 200, page.text[:500])
                self.assertIn("Мониторинг вакансий", page.text)
                self.assertIn("noindex,nofollow", page.text)
                self.assertIn("private, no-store", page.headers["cache-control"])
                self.assertIn("name=\"excluded\"", page.text)
                self.assertIn("hh.ru", page.text)
                csrf = re.search(r'name="csrf_token" value="([^"]+)"', page.text)
                self.assertIsNotNone(csrf)
                changed = client.post("/vacancies/sources", data={
                    "csrf_token": csrf.group(1), "excluded": ["avito.ru", "rosneft.ru"],
                }, follow_redirects=False)
                self.assertEqual(changed.status_code, 303)
                with vacancies.SessionLocal() as db:
                    self.assertEqual(vacancies.disabled_source_names(db), {"avito.ru", "rosneft.ru"})
                page = client.get("/vacancies")
                self.assertIn("Исключён из поиска", page.text)
                csrf = re.search(r'name="csrf_token" value="([^"]+)"', page.text)
                changed = client.post("/vacancies/sources", data={"csrf_token": csrf.group(1)}, follow_redirects=False)
                self.assertEqual(changed.status_code, 303)
                with vacancies.SessionLocal() as db:
                    self.assertEqual(vacancies.disabled_source_names(db), set())
                self.assertIn(client.get("/dashboard", follow_redirects=False).status_code, (303, 401))
                left = client.post("/vacancies/logout", follow_redirects=False)
                self.assertEqual(left.status_code, 303)
                self.assertEqual(client.get("/vacancies", follow_redirects=False).status_code, 303)

if __name__ == "__main__":
    unittest.main()

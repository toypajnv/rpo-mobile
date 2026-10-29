"""Public source parsing must fail closed and never fabricate unverified listings."""
import unittest
from unittest.mock import patch
from app.vacancy_sources import Source, _listing_rows, _avito_rows, safe_url, collect_sources, _robots_allowed

class VacancySourceTests(unittest.TestCase):
    def test_official_gazprom_listing_requires_city_and_title(self):
        html = """<html><body>
          <article><span>Тюменская область, г. Тюмень</span>
            <a href="/vacancies/job/safety-123/">Главный специалист по охране труда</a>
          </article>
          <article><span>Москва</span>
            <a href="/vacancies/job/safety-456/">Главный специалист по охране труда</a>
          </article>
        </body></html>"""
        source = Source("gazpromvacancy.ru", "Газпром",
                        ("https://www.gazpromvacancy.ru/vacancies/",), "www.gazpromvacancy.ru")
        result = _listing_rows(html, source.pages[0], source)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["city"], "Тюмень")
        self.assertIn("safety-123", result[0]["url"])

    def test_link_validation_blocks_external_domains(self):
        page = "https://career.sibur.ru/vacancies/"
        self.assertIsNone(safe_url(page, "https://fake-sibur.example/jobs/123", "career.sibur.ru"))
        self.assertIsNone(safe_url(page, "javascript:alert(1)", "career.sibur.ru"))
        self.assertEqual(safe_url(page, "/vacancies/1", "career.sibur.ru"),
                         "https://career.sibur.ru/vacancies/1")

    def test_avito_requires_explicit_company_location_and_job_title(self):
        html = """<div data-marker="item"> <span>Тюмень</span>
          <span>АО Транснефть-Сибирь</span>
          <a data-marker="item-title" href="/tyumen/vakansii/2345">Специалист по охране труда</a>
        </div>
        <div data-marker="item"> <span>Тюмень</span>
          <span>ООО Неизвестное</span>
          <a data-marker="item-title" href="/tyumen/vakansii/2346">Специалист по охране труда</a>
        </div>"""
        results = _avito_rows(html,"https://www.avito.ru/tyumen/vakansii?q=ot","Тюмень")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["brand"], "Транснефть")

    def test_denied_robots_is_not_bypassed(self):
        with patch("app.vacancy_sources.urlopen") as get:
            response = get.return_value.__enter__.return_value
            response.geturl.return_value = "https://www.avito.ru/robots.txt"
            response.read.return_value = b"User-agent: *\nDisallow: /\n"
            with self.assertRaisesRegex(RuntimeError, "robots.txt"):
                _robots_allowed("https://www.avito.ru/tyumen/vakansii")

    def test_excluded_sites_are_not_requested(self):
        with patch("app.vacancy_sources.fetch_official") as fetch_official, \
             patch("app.vacancy_sources.fetch_avito") as fetch_avito:
            collected, errors = collect_sources({"career.sibur.ru"})
        self.assertEqual(errors, {})
        self.assertEqual(list(collected), ["career.sibur.ru"])
        fetch_official.assert_called_once()
        fetch_avito.assert_not_called()
    def test_one_source_error_does_not_stop_others(self):
        with patch("app.vacancy_sources.fetch_official") as official, \
             patch("app.vacancy_sources.fetch_avito", return_value={}):
            official.side_effect = [RuntimeError("HTTP 403"), {}, {}, {}, {}]
            result, errors = collect_sources()
            self.assertIn("career.sibur.ru", errors)
            self.assertIn("avito.ru", result)

if __name__ == "__main__": unittest.main()
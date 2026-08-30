from pathlib import Path
import unittest

from regressions_core import *  # noqa: F401,F403

# The historical regression suite is preserved verbatim in regressions_core.py.
# Only the static dashboard assertion changes because dashboard.js is now a tiny
# loader and the proven implementation lives in dashboard-core.js.
try:
    del DashboardStaticTests
except NameError:
    pass


class DashboardStaticTests(unittest.TestCase):
    def test_operator_tabs_preview_and_cache_busting(self) -> None:
        server_dir = Path(__file__).resolve().parents[1]
        template = (server_dir / "app/templates/dashboard.html").read_text(encoding="utf-8")
        loader = (server_dir / "app/static/dashboard.js").read_text(encoding="utf-8")
        script = (server_dir / "app/static/dashboard-core.js").read_text(encoding="utf-8")
        ux = (server_dir / "app/static/dashboard-ux.js").read_text(encoding="utf-8")

        for element_id in (
            'id="tab-transmissions"',
            'id="tab-works"',
            'id="tab-analytics"',
            'id="tab-settings"',
            'id="export-form"',
            'id="preview-modal"',
            'id="preview-list"',
            'id="confirm-export-form"',
            'id="confirm-send"',
        ):
            self.assertIn(element_id, template)
        self.assertIn('href="#settings"', template)
        self.assertIn('href="#analytics"', template)
        self.assertIn('data-tab-link="transmissions"', template)
        self.assertIn('data-tab-link="works"', template)
        self.assertIn("Один наряд-допуск — одна строка", template)
        self.assertIn("Ранее выгруженные НД тоже можно", template)
        self.assertIn("dashboard.js?v=20260829-2", template)
        self.assertIn("app.css?v=20260829-3", template)
        self.assertIn("dashboard-core.js?v=20260830-1", loader)
        self.assertIn("dashboard-ux.js?v=20260830-1", loader)
        self.assertIn("preview-table", script)
        self.assertIn("stageDetails", script)
        self.assertIn("Показать детали", script)
        self.assertIn("За выбранный период и текущий фильтр нет нарядов-допусков.", script)
        self.assertNotIn("нет невыгруженных нарядов-допусков", script)
        self.assertIn("window.scrollTo", script)
        self.assertIn("exportForm?.addEventListener('submit'", script)
        self.assertIn("modal.hidden=false", script.replace(" ", ""))
        self.assertIn("/api/operator/transmissions", script)
        self.assertIn("/api/operator/events", script)
        self.assertIn("Требуют внимания", ux)
        self.assertIn("ux-drawer", ux)


if __name__ == "__main__":
    unittest.main()

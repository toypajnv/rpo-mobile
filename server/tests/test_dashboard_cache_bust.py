from __future__ import annotations

import unittest

from app import main


class DashboardCacheBustTests(unittest.TestCase):
    def test_dashboard_loader_revision_forces_fresh_operator_controls(self) -> None:
        self.assertEqual(main.DASHBOARD_ASSET_VERSION, "20260901-2")
        source, _, _ = main._core.templates.env.loader.get_source(
            main._core.templates.env, "dashboard.html"
        )
        self.assertIn('/static/dashboard.js?v=20260901-2', source)
        self.assertIn('/static/dashboard-decisions.js?v=20260901-2', source)
        self.assertNotIn('/static/dashboard.js?v=20260829-2', source)
        self.assertNotIn('/static/dashboard.js?v=20260831-2', source)

    def test_decision_controls_are_direct_not_async_loader_dependency(self) -> None:
        loader = (main._core.BASE_DIR / "static" / "dashboard.js").read_text(encoding="utf-8")
        decisions = (main._core.BASE_DIR / "static" / "dashboard-decisions.js").read_text(encoding="utf-8")
        self.assertNotIn(".then(() => load('/static/dashboard-decisions.js", loader)
        self.assertIn('data-rpo-decision="denied"', decisions)
        self.assertIn("Запретить", decisions)
        self.assertIn("/decision", decisions)

    def test_decision_controls_reapply_immediately_after_core_table_refresh(self) -> None:
        decisions = (main._core.BASE_DIR / "static" / "dashboard-decisions.js").read_text(encoding="utf-8")
        self.assertIn("function bindTableObservers()", decisions)
        self.assertIn("new MutationObserver(() => queueMicrotask(annotateSnapshot))", decisions)
        self.assertIn("observe(body, {childList:true})", decisions)
        self.assertNotIn("subtree:true", decisions)


if __name__ == "__main__":
    unittest.main()

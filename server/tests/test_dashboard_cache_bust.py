from __future__ import annotations

import unittest

from app import main


class DashboardCacheBustTests(unittest.TestCase):
    def test_dashboard_loader_revision_forces_fresh_operator_controls(self) -> None:
        self.assertEqual(main.DASHBOARD_ASSET_VERSION, "20260909-3")
        source, _, _ = main._core.templates.env.loader.get_source(
            main._core.templates.env, "dashboard.html"
        )
        self.assertIn('/static/dashboard.js?v=20260909-3', source)
        self.assertIn('/static/dashboard-decisions.js?v=20260909-3', source)
        self.assertNotIn('/static/dashboard.js?v=20260829-2', source)
        self.assertNotIn('/static/dashboard.js?v=20260831-2', source)

    def test_pending_decision_controls_and_lift_prohibition_action(self) -> None:
        loader = (main._core.BASE_DIR / "static" / "dashboard.js").read_text(encoding="utf-8")
        decisions = (main._core.BASE_DIR / "static" / "dashboard-decisions.js").read_text(encoding="utf-8")
        self.assertNotIn(".then(() => load('/static/dashboard-decisions.js", loader)
        self.assertIn('data-rpo-decision="approved"', decisions)
        self.assertIn('data-rpo-decision="denied"', decisions)
        self.assertIn('data-rpo-lift="true"', decisions)
        self.assertIn("approval_status === 'pending'", decisions)
        self.assertIn("approval_status === 'denied'", decisions)
        self.assertIn("Запретить работы", decisions)
        self.assertIn("Разрешить", decisions)
        self.assertIn("Снять запрет", decisions)
        self.assertIn("Снимаю запрет…", decisions)
        self.assertIn("/decision", decisions)
        self.assertIn("permit-decision-controls", decisions)
        self.assertIn("transmission-deny-control", decisions)
        self.assertIn("#transmissions-body .review-controls{display:none!important}", decisions)

    def test_controls_are_reapplied_without_visible_review_button_race(self) -> None:
        decisions = (main._core.BASE_DIR / "static" / "dashboard-decisions.js").read_text(encoding="utf-8")
        self.assertIn("function bindTableObservers()", decisions)
        self.assertIn("new MutationObserver(() => queueMicrotask(annotateSnapshot))", decisions)
        self.assertIn("new MutationObserver(queueTransmissionAnnotation)", decisions)
        self.assertIn("observe(worksBody, {childList:true})", decisions)
        self.assertIn("observe(transmissionsBody, {childList:true, subtree:true})", decisions)
        self.assertIn("transmissionAnnotationQueued", decisions)
        self.assertIn("removeLegacyFinishButtons", decisions)
        self.assertIn("завершить работы", decisions)
        self.assertIn("data-rpo-control-mode", decisions)


if __name__ == "__main__":
    unittest.main()

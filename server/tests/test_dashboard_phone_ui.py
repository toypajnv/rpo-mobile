from __future__ import annotations

import unittest

from app import main


class DashboardPhoneUiTests(unittest.TestCase):
    def test_phone_assets_are_injected_without_replacing_tablet_layout(self) -> None:
        self.assertEqual(main.DASHBOARD_PHONE_VERSION, "20260903-1")
        source, _, _ = main._core.templates.env.loader.get_source(
            main._core.templates.env, "dashboard.html"
        )
        self.assertIn('id="dashboard-phone-detect"', source)
        self.assertIn("shortSide <= 540", source)
        self.assertIn("(pointer: coarse)", source)
        self.assertIn(
            '/static/dashboard-mobile.css?v=20260903-1',
            source,
        )
        self.assertIn(
            '/static/dashboard-mobile.js?v=20260903-1',
            source,
        )
        # The original sidebar stays in the HTML: desktop and tablets keep the
        # existing interface because the phone class is never applied to them.
        self.assertIn('class="sidebar"', source)
        self.assertIn('data-tab-link="works"', source)

    def test_server_release_advances_for_mobile_dashboard(self) -> None:
        self.assertEqual(main._core.app.version, "0.7.4")
        self.assertEqual(main.LATEST_MOBILE_VERSION, "2.2.2")
        self.assertEqual(main.PWA_VERSION, "1.2.2")


if __name__ == "__main__":
    unittest.main()

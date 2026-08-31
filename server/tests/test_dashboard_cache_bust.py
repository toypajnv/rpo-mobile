from __future__ import annotations

import unittest

from app import main


class DashboardCacheBustTests(unittest.TestCase):
    def test_dashboard_loader_revision_forces_fresh_operator_controls(self) -> None:
        self.assertEqual(main.DASHBOARD_ASSET_VERSION, "20260831-2")
        source, _, _ = main._core.templates.env.loader.get_source(
            main._core.templates.env, "dashboard.html"
        )
        self.assertIn('/static/dashboard.js?v=20260831-2', source)
        self.assertNotIn('/static/dashboard.js?v=20260829-2', source)


if __name__ == "__main__":
    unittest.main()

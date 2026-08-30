from pathlib import Path
import unittest

from app import main


SERVER_DIR = Path(__file__).resolve().parents[1]
APP_DIR = SERVER_DIR / "app"


class Ux21AssetsTest(unittest.TestCase):
    def test_public_versions_are_updated_without_breaking_legacy_support(self):
        self.assertEqual(main.app.version, "0.6.0")
        self.assertEqual(main.LATEST_MOBILE_VERSION, "2.1.0")
        self.assertEqual(main.PWA_VERSION, "1.1.1")
        self.assertEqual(main.MIN_SUPPORTED_MOBILE_VERSION, "1.0.1")
        self.assertIn("v2.1.0-test/rpo-mobile-2.1.0.apk", main.MOBILE_APK_URL)

    def test_dashboard_core_is_preserved_and_new_ux_is_layered(self):
        loader = (APP_DIR / "static" / "dashboard.js").read_text(encoding="utf-8")
        core = (APP_DIR / "static" / "dashboard-core.js").read_text(encoding="utf-8")
        ux = (APP_DIR / "static" / "dashboard-ux.js").read_text(encoding="utf-8")
        self.assertIn("dashboard-core.js?v=20260830-1", loader)
        self.assertIn("dashboard-ux.js?v=20260830-1", loader)
        self.assertIn("refreshWorks", core)
        self.assertIn("Требуют внимания", ux)
        self.assertIn("ux-drawer", ux)

    def test_pwa_ux_111_assets_are_installable_cached_and_ios_safe(self):
        index = (APP_DIR / "pwa" / "index.html").read_text(encoding="utf-8")
        sw = (APP_DIR / "pwa" / "sw.js").read_text(encoding="utf-8")
        ux = (APP_DIR / "pwa" / "ux.js").read_text(encoding="utf-8")
        self.assertIn("PWA 1.1.1", index)
        self.assertIn("/pwa-assets/ux.js?v=20260830-2", index)
        self.assertIn("rpo-pwa-shell-v1.1.1", sw)
        self.assertIn("Следующее действие", ux)
        self.assertIn("history-search", ux)
        self.assertIn("pageshow", ux)
        self.assertIn("dispatchEvent(new Event('input'", ux)
        self.assertNotIn("observe(stageFields", ux)
        self.assertNotIn("ux-next-open", ux)


if __name__ == "__main__":
    unittest.main()

from pathlib import Path
import unittest

from app import main


SERVER_DIR = Path(__file__).resolve().parents[1]
APP_DIR = SERVER_DIR / "app"


class Ux21AssetsTest(unittest.TestCase):
    def test_public_versions_are_updated_without_breaking_legacy_support(self):
        self.assertEqual(main.app.version, "0.7.0")
        self.assertEqual(main.LATEST_MOBILE_VERSION, "2.2.0")
        self.assertEqual(main.PWA_VERSION, "1.2.0")
        self.assertEqual(main.MIN_SUPPORTED_MOBILE_VERSION, "1.0.1")
        self.assertIn("v2.2.0-test/rpo-mobile-2.2.0.apk", main.MOBILE_APK_URL)

    def test_dashboard_core_is_preserved_and_operator_decisions_are_layered(self):
        loader = (APP_DIR / "static" / "dashboard.js").read_text(encoding="utf-8")
        core = (APP_DIR / "static" / "dashboard-core.js").read_text(encoding="utf-8")
        ux = (APP_DIR / "static" / "dashboard-ux.js").read_text(encoding="utf-8")
        decisions = (APP_DIR / "static" / "dashboard-decisions.js").read_text(encoding="utf-8")
        self.assertIn("dashboard-core.js?v=20260830-1", loader)
        self.assertIn("dashboard-ux.js?v=20260830-1", loader)
        self.assertIn("dashboard-decisions.js?v=20260831-1", loader)
        self.assertIn("refreshWorks", core)
        self.assertIn("Требуют внимания", ux)
        self.assertIn("ux-drawer", ux)
        self.assertIn('data-rpo-decision="denied"', decisions)
        self.assertIn('/decision', decisions)
        self.assertIn('ПРОВЕДЕНИЕ ЗАПРЕЩЕНО', decisions)
        self.assertIn('Причина запрета', decisions)

    def test_pwa_ux_120_assets_are_installable_cached_and_fail_safe(self):
        index = (APP_DIR / "pwa" / "index.html").read_text(encoding="utf-8")
        sw = (APP_DIR / "pwa" / "sw.js").read_text(encoding="utf-8")
        ux = (APP_DIR / "pwa" / "ux.js").read_text(encoding="utf-8")
        sync = (APP_DIR / "pwa" / "sync-status.js").read_text(encoding="utf-8")
        deny = (APP_DIR / "pwa" / "deny-lock.js").read_text(encoding="utf-8")
        self.assertIn("PWA 1.2.0", index)
        self.assertIn("/pwa-assets/ux.js?v=20260830-2", index)
        self.assertIn("/pwa-assets/sync-status.js?v=20260831-1", index)
        self.assertIn("/pwa-assets/deny-lock.js?v=20260831-1", index)
        self.assertIn("rpo-pwa-shell-v1.2.0", sw)
        self.assertIn("sync-status.js?v=20260831-1", sw)
        self.assertIn("deny-lock.js?v=20260831-1", sw)
        self.assertIn("Следующее действие", ux)
        self.assertIn("history-search", ux)
        self.assertIn("pageshow", ux)
        self.assertIn("dispatchEvent(new Event('input'", ux)
        self.assertNotIn("observe(stageFields", ux)
        self.assertNotIn("ux-next-open", ux)
        self.assertIn("Ошибка передачи на сервер", sync)
        self.assertIn("До подтверждения сервера этап не считается переданным", sync)
        self.assertIn("nativeRemoveItem.call(localStorage, SAVED_KEY)", sync)
        self.assertIn("ПРОВЕДЕНИЕ РАБОТ ЗАПРЕЩЕНО", deny)
        self.assertIn("rpo_pwa_denied_permit_v1", deny)


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import unittest

from app import main


class PwaPermitEntryHotfixTests(unittest.TestCase):
    def test_permit_editor_does_not_auto_collapse_after_three_symbols(self) -> None:
        self.assertEqual(main.PWA_ENTRY_HOTFIX_VERSION, "20260901-1")
        source = (main._core.PWA_DIR / "permit-entry-hotfix.js").read_text(encoding="utf-8")
        self.assertIn("permit.addEventListener('focus'", source)
        self.assertIn("permit.addEventListener('input'", source)
        self.assertIn("formCard.dataset.uxCollapsedOnce = '1'", source)
        self.assertIn("formCard.classList.remove('ux-collapsed')", source)
        self.assertIn("▴ Свернуть", source)

    def test_pwa_html_hotfix_is_injected_by_server(self) -> None:
        main_source = (main._core.BASE_DIR / "main.py").read_text(encoding="utf-8")
        self.assertIn('/pwa-assets/permit-entry-hotfix.js?v={PWA_ENTRY_HOTFIX_VERSION}', main_source)
        self.assertIn('request.url.path == "/app/"', main_source)
        self.assertIn('"Cache-Control": "no-store, no-cache, must-revalidate, max-age=0"', main_source)


if __name__ == "__main__":
    unittest.main()

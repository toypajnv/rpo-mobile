from pathlib import Path
import unittest


class PwaBottomSafeAreaTests(unittest.TestCase):
    def test_bottom_navigation_keeps_four_tabs_on_one_row(self) -> None:
        root = Path(__file__).resolve().parents[2]
        main = (root / "server/app/main.py").read_text(encoding="utf-8")
        self.assertIn("grid-template-columns:repeat(4,minmax(0,1fr))", main)

    def test_main_content_reserves_bottom_nav_and_ios_safe_area(self) -> None:
        root = Path(__file__).resolve().parents[2]
        main = (root / "server/app/main.py").read_text(encoding="utf-8")
        self.assertIn("env(safe-area-inset-bottom, 0px)", main)
        self.assertIn("padding-bottom:calc(112px + env(safe-area-inset-bottom, 0px))", main)
        self.assertIn("#tab-instruction .instruction-shell{padding-bottom:24px}", main)
        self.assertIn('id=\\"pwa-bottom-safe-area\\"', main)


if __name__ == "__main__":
    unittest.main()

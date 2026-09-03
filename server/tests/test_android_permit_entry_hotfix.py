from pathlib import Path
import unittest


class AndroidPermitEntryHotfixTests(unittest.TestCase):
    def test_permit_editor_does_not_collapse_after_third_symbol(self) -> None:
        root = Path(__file__).resolve().parents[2]
        source = (root / "android/app/src/main/java/ru/rpo/mobile/ui/RpoUxApp.kt").read_text(encoding="utf-8")
        self.assertIn("var editDetails by remember { mutableStateOf(!permitReady) }", source)
        self.assertNotIn("var editDetails by remember(s.permitNumber)", source)
        self.assertNotIn("LaunchedEffect(permitReady)", source)

    def test_android_hotfix_version_is_2_2_2(self) -> None:
        root = Path(__file__).resolve().parents[2]
        gradle = (root / "android/app/build.gradle.kts").read_text(encoding="utf-8")
        self.assertIn('versionCode = 15', gradle)
        self.assertIn('versionName = "2.2.2"', gradle)


if __name__ == "__main__":
    unittest.main()

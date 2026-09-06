from pathlib import Path
import unittest


class InstructionAssistantTests(unittest.TestCase):
    def setUp(self) -> None:
        self.root = Path(__file__).resolve().parents[2]
        self.pwa = self.root / "server/app/pwa"
        self.android = self.root / "android/app/src/main/java/ru/rpo/mobile/ui"

    def test_android_has_instruction_tab_and_five_step_assistant(self) -> None:
        app = (self.android / "RpoUxApp.kt").read_text(encoding="utf-8")
        assistant = (self.android / "InstructionAssistant.kt").read_text(encoding="utf-8")
        gradle = (self.root / "android/app/build.gradle.kts").read_text(encoding="utf-8")

        self.assertIn("UxTab.INSTRUCTION", app)
        self.assertIn('Text("Инструктаж")', app)
        self.assertIn("Помощник при инструктаже", assistant)
        self.assertIn("РОИ — модель проведения инструктажа", assistant)
        self.assertIn("Инструктаж: шаг $step из 5", assistant)
        self.assertIn("Обсудите характер предстоящей работы", assistant)
        self.assertIn("Определите основные опасности", assistant)
        self.assertIn("Обсудите меры безопасности", assistant)
        self.assertIn("Обсудите действия в нештатной ситуации", assistant)
        self.assertIn("Определите готовность приступить к безопасному выполнению работ", assistant)
        self.assertIn("Мини-база знаний", assistant)
        self.assertIn('versionName = "2.3.0"', gradle)

    def test_ios_pwa_has_instruction_tab_assets_and_offline_cache(self) -> None:
        index = (self.pwa / "index.html").read_text(encoding="utf-8")
        script = (self.pwa / "instruction-assistant.js").read_text(encoding="utf-8")
        css = (self.pwa / "instruction-assistant.css").read_text(encoding="utf-8")
        sw = (self.pwa / "sw.js").read_text(encoding="utf-8")
        app_js = (self.pwa / "app.js").read_text(encoding="utf-8")

        self.assertIn('data-screen="instruction"', index)
        self.assertIn('data-tab="instruction"', index)
        self.assertIn('/pwa-assets/instruction-assistant.js?v=20260906-1', index)
        self.assertIn('/pwa-assets/instruction-assistant.css?v=20260906-1', index)
        self.assertIn("Помощник при инструктаже", script)
        self.assertIn("Когда нужен повторный инструктаж", script)
        self.assertIn("Пять шагов безопасности / РОИ", script)
        self.assertIn("instruction-risk-grid", css)
        self.assertIn("rpo-pwa-shell-v1.3.0", sw)
        self.assertIn("instruction-assistant.js?v=20260906-1", sw)
        self.assertIn("instruction-assistant.css?v=20260906-1", sw)
        self.assertIn("const PWA_VERSION = '1.3.0'", app_js)


if __name__ == "__main__":
    unittest.main()

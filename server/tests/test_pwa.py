import json
from pathlib import Path
import unittest

from fastapi.testclient import TestClient

from app.main import app


class PwaStaticTests(unittest.TestCase):
    def setUp(self) -> None:
        self.server_dir = Path(__file__).resolve().parents[1]
        self.pwa_dir = self.server_dir / "app" / "pwa"

    def test_pwa_shell_contains_install_offline_and_approval_features(self) -> None:
        html = (self.pwa_dir / "index.html").read_text(encoding="utf-8")
        js = (self.pwa_dir / "app.js").read_text(encoding="utf-8")
        ux = (self.pwa_dir / "ux.js").read_text(encoding="utf-8")
        sync = (self.pwa_dir / "sync-status.js").read_text(encoding="utf-8")
        deny = (self.pwa_dir / "deny-lock.js").read_text(encoding="utf-8")
        sw = (self.pwa_dir / "sw.js").read_text(encoding="utf-8")
        manifest = json.loads((self.pwa_dir / "manifest.webmanifest").read_text(encoding="utf-8"))

        self.assertIn('apple-mobile-web-app-capable', html)
        self.assertIn('/app/manifest.webmanifest', html)
        self.assertIn('На экран Домой', html)
        self.assertIn('rpo_pwa_queue_v1', js)
        self.assertIn("window.addEventListener('online'", js)
        self.assertIn("setInterval", js)
        self.assertIn('/api/mobile/events', js)
        self.assertIn('/api/mobile/permit', js)
        self.assertIn('/api/mobile/permit-suggestions', js)
        self.assertIn('permit-suggestion-menu', html)
        self.assertIn('hasStageDraft', js)
        self.assertIn('noNewEvents', js)
        self.assertIn('history-details', js)
        self.assertIn('Ожидает разрешения', js)
        self.assertIn('Работы можно проводить', js)
        self.assertIn('ЦДПН-1', js)
        self.assertIn('Замена исполнителей работ', js)
        self.assertIn('Следующее действие', ux)
        self.assertIn('history-search', ux)
        self.assertIn('/pwa-assets/sync-status.js?v=20260831-1', html)
        self.assertIn('/pwa-assets/sync-status.js?v=20260831-1', sw)
        self.assertIn('/pwa-assets/deny-lock.js?v=20260831-1', html)
        self.assertIn('/pwa-assets/deny-lock.js?v=20260831-1', sw)
        self.assertIn("const CACHE='rpo-pwa-shell-v1.2.0'", sw)
        self.assertIn('Ошибка передачи на сервер', sync)
        self.assertIn('ПРОВЕДЕНИЕ РАБОТ ЗАПРЕЩЕНО', deny)
        self.assertIn('rpo_pwa_denied_permit_v1', deny)
        self.assertEqual(manifest['start_url'], '/app/')
        self.assertEqual(manifest['scope'], '/app/')
        self.assertEqual(manifest['display'], 'standalone')
        self.assertEqual({icon['sizes'] for icon in manifest['icons']}, {'192x192', '512x512'})

    def test_ios_hotfix_prevents_render_loop_and_revalidates_native_date_change(self) -> None:
        html = (self.pwa_dir / "index.html").read_text(encoding="utf-8")
        ux = (self.pwa_dir / "ux.js").read_text(encoding="utf-8")
        sw = (self.pwa_dir / "sw.js").read_text(encoding="utf-8")

        self.assertIn("window.addEventListener('pageshow'", ux)
        self.assertIn("document.addEventListener('visibilitychange'", ux)
        self.assertIn("event.target.dispatchEvent(new Event('input'", ux)
        self.assertNotIn("observe(stageFields", ux)
        self.assertIn("note.dataset.message = text", ux)
        self.assertNotIn('ux-next-open', ux)
        self.assertIn('Переходить между этапами можно сразу', html)
        self.assertIn('/pwa-assets/ux.js?v=20260830-2', html)
        self.assertIn('/pwa-assets/ux.js?v=20260830-2', sw)

    def test_transmission_status_requires_server_confirmation_and_explains_failures(self) -> None:
        html = (self.pwa_dir / "index.html").read_text(encoding="utf-8")
        sync = (self.pwa_dir / "sync-status.js").read_text(encoding="utf-8")

        self.assertIn("const SAVED_KEY = 'rpo_pwa_saved_v1'", sync)
        self.assertIn('nativeRemoveItem.call(localStorage, SAVED_KEY)', sync)
        self.assertIn('key === SAVED_KEY', sync)
        self.assertIn('Server-confirmed fields remain the only source', sync)
        self.assertIn('pendingKeys', sync)
        self.assertIn('Ошибка передачи на сервер', sync)
        self.assertIn('До подтверждения сервера этап не считается переданным', sync)
        self.assertIn("button.textContent = 'Исправить'", sync)
        self.assertIn('event.stopImmediatePropagation()', sync)
        self.assertIn('restoreFailedPayload', sync)
        self.assertIn('Если оператор запретит проведение работ по любому этапу', html)
        self.assertIn('PWA 1.2.0', html)

    def test_operator_denial_is_a_full_screen_fail_safe_lock(self) -> None:
        html = (self.pwa_dir / "index.html").read_text(encoding="utf-8")
        deny = (self.pwa_dir / "deny-lock.js").read_text(encoding="utf-8")

        self.assertIn('Решение оператора', html)
        self.assertIn('блокирует весь выбранный НД', html)
        self.assertIn("approval?.status === 'denied'", deny)
        self.assertIn("const CACHE_KEY = 'rpo_pwa_denied_permit_v1'", deny)
        self.assertIn('ПРОВЕДЕНИЕ РАБОТ ЗАПРЕЩЕНО', deny)
        self.assertIn('Не продолжайте работы по этому наряду-допуску', deny)
        self.assertIn('Выбрать другой НД', deny)
        self.assertIn('При отсутствии сети ранее полученный запрет сохраняется', deny)
        self.assertIn("setInterval", deny)

    def test_pwa_routes_and_icons_are_served(self) -> None:
        with TestClient(app) as client:
            response = client.get('/app', follow_redirects=False)
            self.assertEqual(response.status_code, 307)
            self.assertEqual(response.headers['location'], '/app/')

            page = client.get('/app/')
            self.assertEqual(page.status_code, 200)
            self.assertIn('РПО — работы повышенной опасности', page.text)
            self.assertIn('no-cache', page.headers.get('cache-control', ''))

            sync = client.get('/pwa-assets/sync-status.js')
            self.assertEqual(sync.status_code, 200)
            self.assertIn('Ошибка передачи на сервер', sync.text)

            deny = client.get('/pwa-assets/deny-lock.js')
            self.assertEqual(deny.status_code, 200)
            self.assertIn('ПРОВЕДЕНИЕ РАБОТ ЗАПРЕЩЕНО', deny.text)

            manifest = client.get('/app/manifest.webmanifest')
            self.assertEqual(manifest.status_code, 200)
            self.assertEqual(manifest.json()['start_url'], '/app/')

            worker = client.get('/app/sw.js')
            self.assertEqual(worker.status_code, 200)
            self.assertEqual(worker.headers.get('service-worker-allowed'), '/app/')

            for size in (180, 192, 512):
                icon = client.get(f'/app/icon-{size}.png')
                self.assertEqual(icon.status_code, 200)
                self.assertEqual(icon.headers.get('content-type'), 'image/png')
                self.assertTrue(icon.content.startswith(b'\x89PNG\r\n\x1a\n'))

            self.assertEqual(client.get('/app/icon-256.png').status_code, 404)

    def test_mobile_config_advertises_decision_release_without_forcing_update(self) -> None:
        with TestClient(app) as client:
            response = client.get('/api/mobile/config?app_version=1.0.1')
            self.assertEqual(response.status_code, 200)
            data = response.json()
            self.assertEqual(data['latest_app_version'], '2.2.0')
            self.assertFalse(data['update_required'])
            self.assertEqual(data['pwa_version'], '1.2.0')
            self.assertEqual(data['pwa_url'], 'https://rpo-mng.ru/app/')
            self.assertEqual(data['server_version'], '0.7.0')


if __name__ == '__main__':
    unittest.main()

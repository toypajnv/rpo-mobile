from pathlib import Path
import unittest

from fastapi.testclient import TestClient

from app.main import app


APP_DIR = Path(__file__).resolve().parents[1] / "app"
PWA_DIR = APP_DIR / "pwa"


class PwaStaticTests(unittest.TestCase):
    def test_pwa_shell_contains_install_offline_and_approval_features(self) -> None:
        html = (PWA_DIR / "index.html").read_text(encoding="utf-8")
        js = (PWA_DIR / "app.js").read_text(encoding="utf-8")
        ux = (PWA_DIR / "ux.js").read_text(encoding="utf-8")
        sync = (PWA_DIR / "sync-status.js").read_text(encoding="utf-8")
        sw = (PWA_DIR / "sw.js").read_text(encoding="utf-8")
        self.assertIn('apple-mobile-web-app-capable', html)
        self.assertIn('/app/manifest.webmanifest', html)
        self.assertIn('На экран Домой', html)
        self.assertIn('permit-suggestion-menu', html)
        self.assertIn('Проверить', html)
        self.assertIn('История', html)
        self.assertIn('Ожидает разрешения', ux)
        self.assertIn('До подтверждения сервера этап не считается переданным', sync)
        self.assertIn("button.textContent = 'Исправить'", sync)
        self.assertIn("rpo-pwa-shell-v1.2.1", sw)

    def test_ios_hotfix_prevents_render_loop_and_revalidates_native_date_change(self) -> None:
        ux = (PWA_DIR / "ux.js").read_text(encoding="utf-8")
        self.assertNotIn('observe(stageFields', ux)
        self.assertNotIn('ux-next-open', ux)
        self.assertIn("window.addEventListener('pageshow'", ux)
        self.assertIn("event.target.dispatchEvent(new Event('input'", ux)

    def test_operator_denial_is_a_full_screen_fail_safe_lock(self) -> None:
        deny = (PWA_DIR / "deny-lock.js").read_text(encoding="utf-8")
        self.assertIn("const CACHE_KEY = 'rpo_pwa_denied_permit_v1'", deny)
        self.assertIn('ПРОВЕДЕНИЕ РАБОТ ЗАПРЕЩЕНО', deny)
        self.assertIn("approval?.status === 'denied'", deny)
        self.assertIn('Выбрать другой НД', deny)
        self.assertIn('При отсутствии сети ранее полученный запрет сохраняется', deny)

    def test_transmission_status_requires_server_confirmation_and_explains_failures(self) -> None:
        sync = (PWA_DIR / "sync-status.js").read_text(encoding="utf-8")
        self.assertIn("const SAVED_KEY = 'rpo_pwa_saved_v1'", sync)
        self.assertIn('nativeRemoveItem.call(localStorage, SAVED_KEY)', sync)
        self.assertIn('Ошибка передачи на сервер', sync)
        self.assertIn('До подтверждения сервера этап не считается переданным', sync)
        self.assertIn("button.textContent = 'Исправить'", sync)

    def test_pwa_routes_and_icons_are_served(self) -> None:
        with TestClient(app) as client:
            response = client.get('/app', follow_redirects=False)
            self.assertEqual(response.status_code, 307)
            self.assertEqual(response.headers.get('location'), '/app/')

            html = client.get('/app/')
            self.assertEqual(html.status_code, 200)
            self.assertIn('PWA 1.2.1', html.text)
            self.assertIn('/pwa-assets/sync-status.js?v=20260831-1', html.text)
            self.assertIn('/pwa-assets/deny-lock.js?v=20260831-1', html.text)
            self.assertIn('/pwa-assets/history-status.js?v=20260901-1', html.text)
            self.assertIn('Если оператор запретит проведение работ по любому этапу', html.text)

            self.assertEqual(client.get('/pwa-assets/sync-status.js').status_code, 200)
            self.assertEqual(client.get('/pwa-assets/deny-lock.js').status_code, 200)
            self.assertEqual(client.get('/pwa-assets/history-status.js').status_code, 200)

            manifest = client.get('/app/manifest.webmanifest')
            self.assertEqual(manifest.status_code, 200)
            data = manifest.json()
            self.assertEqual(data['start_url'], '/app/')
            self.assertEqual(data['scope'], '/app/')
            self.assertEqual(data['display'], 'standalone')
            sizes = {icon['sizes'] for icon in data['icons']}
            self.assertTrue({'192x192', '512x512'} <= sizes)

            service_worker = client.get('/app/sw.js')
            self.assertEqual(service_worker.status_code, 200)
            self.assertIn('service-worker-allowed', {k.lower() for k in service_worker.headers})
            self.assertEqual(service_worker.headers['service-worker-allowed'], '/app/')
            self.assertIn('rpo-pwa-shell-v1.2.1', service_worker.text)

            self.assertEqual(client.get('/app/icon-180.png').status_code, 200)
            self.assertEqual(client.get('/app/icon-192.png').status_code, 200)
            self.assertEqual(client.get('/app/icon-512.png').status_code, 200)
            self.assertEqual(client.get('/app/icon-256.png').status_code, 404)

    def test_mobile_config_advertises_decision_release_without_forcing_update(self) -> None:
        with TestClient(app) as client:
            response = client.get('/api/mobile/config?app_version=1.0.1')
            self.assertEqual(response.status_code, 200)
            data = response.json()
            self.assertEqual(data['latest_app_version'], '2.2.2')
            self.assertFalse(data['update_required'])
            self.assertEqual(data['pwa_version'], '1.2.1')
            self.assertEqual(data['pwa_url'], 'https://rpo-mng.ru/app/')
            self.assertEqual(data['server_version'], '0.7.3')


if __name__ == '__main__':
    unittest.main()

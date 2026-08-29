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
        self.assertIn('Ожидает разрешения', js)
        self.assertIn('Работы можно проводить', js)
        self.assertIn('ЦДПН-1', js)
        self.assertIn('Замена исполнителей работ', js)
        self.assertIn("const CACHE='rpo-pwa-shell-v1.0.0'", sw)
        self.assertEqual(manifest['start_url'], '/app/')
        self.assertEqual(manifest['scope'], '/app/')
        self.assertEqual(manifest['display'], 'standalone')
        self.assertEqual({icon['sizes'] for icon in manifest['icons']}, {'192x192', '512x512'})

    def test_pwa_routes_and_icons_are_served(self) -> None:
        with TestClient(app) as client:
            response = client.get('/app', follow_redirects=False)
            self.assertEqual(response.status_code, 307)
            self.assertEqual(response.headers['location'], '/app/')

            page = client.get('/app/')
            self.assertEqual(page.status_code, 200)
            self.assertIn('РПО — работы повышенной опасности', page.text)
            self.assertIn('no-cache', page.headers.get('cache-control', ''))

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

    def test_mobile_config_advertises_pwa_without_changing_android_contract(self) -> None:
        with TestClient(app) as client:
            response = client.get('/api/mobile/config?app_version=1.0.1')
            self.assertEqual(response.status_code, 200)
            data = response.json()
            self.assertEqual(data['latest_app_version'], '2.0.0')
            self.assertFalse(data['update_required'])
            self.assertEqual(data['pwa_version'], '1.0.0')
            self.assertEqual(data['pwa_url'], 'https://rpo-mng.ru/app/')
            self.assertEqual(data['server_version'], '0.5.1')


if __name__ == '__main__':
    unittest.main()

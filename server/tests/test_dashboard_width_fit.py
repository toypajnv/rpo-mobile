from pathlib import Path
import unittest


class DashboardWidthFitTests(unittest.TestCase):
    def test_operational_tables_fit_desktop_width(self) -> None:
        server_dir = Path(__file__).resolve().parents[1]
        css = (server_dir / "app/static/app.css").read_text(encoding="utf-8")
        html = (server_dir / "app/templates/dashboard.html").read_text(encoding="utf-8")

        self.assertIn("Dashboard desktop width fit v2.0.1", css)
        self.assertIn("#tab-transmissions .table-wrap,#tab-works .table-wrap{overflow-x:hidden}", css)
        self.assertIn("width:100%;table-layout:fixed;white-space:normal", css)
        self.assertIn("overflow-wrap:anywhere", css)
        self.assertIn("#tab-transmissions .wrap-cell,#tab-works .works-stage-cell{min-width:0}", css)
        self.assertIn("#tab-works .stage-detail-line{grid-template-columns:1fr", css)
        self.assertIn("/static/app.css?v=20260829-3", html)


if __name__ == "__main__":
    unittest.main()

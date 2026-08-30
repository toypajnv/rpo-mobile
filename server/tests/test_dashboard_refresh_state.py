from pathlib import Path
import unittest


class DashboardRefreshStateTests(unittest.TestCase):
    def test_open_work_details_survive_live_refresh(self) -> None:
        server_dir = Path(__file__).resolve().parents[1]
        script = (server_dir / "app/static/dashboard-core.js").read_text(encoding="utf-8")

        self.assertIn("details.stage-details[open]", script)
        self.assertIn("openPermits", script)
        self.assertIn("data-permit", script)
        self.assertIn("openPermits.has(e.permit_number)", script)


if __name__ == "__main__":
    unittest.main()

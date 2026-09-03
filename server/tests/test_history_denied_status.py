from __future__ import annotations

import unittest
from datetime import datetime, timezone

from app import main
from app.database import Base, SessionLocal, engine
from app.decision_control import EventDecisionRequest
from app.models import Operator
from app.schemas import EventCreate


class HistoryDeniedStatusTests(unittest.TestCase):
    def setUp(self) -> None:
        Base.metadata.drop_all(engine)
        Base.metadata.create_all(engine)

    def tearDown(self) -> None:
        Base.metadata.drop_all(engine)

    def test_history_uses_permit_wide_denial_and_recovers_after_allow(self) -> None:
        with SessionLocal() as db:
            event = main.create_mobile_event(EventCreate(
                client_event_id="history-denied-status-0001",
                device_id="ios-history-denied",
                worker_name="Горбач ИА",
                structural_unit="ЦДПН-1",
                permit_number="888899",
                field_key="AT",
                stage_label="Начало подготовки",
                event_time=datetime.now(timezone.utc),
                field_value="01.09.2026 09:11",
                comment="",
            ), db)
            operator = Operator(username="Operator", password_hash="x", is_active=True)
            db.add(operator)
            db.commit()

            main.decide_mobile_event(
                event.id,
                EventDecisionRequest(decision="denied", reason="Не выполнены меры безопасности"),
                operator=operator,
                db=db,
            )
            denied = main.mobile_history("ios-history-denied", 30, db)
            self.assertEqual(len(denied), 1)
            self.assertEqual(denied[0]["approval_status"], "denied")
            self.assertIn("Проведение работ запрещено", denied[0]["comment"])
            self.assertIn("Не выполнены меры безопасности", denied[0]["comment"])

            main.decide_mobile_event(
                event.id,
                EventDecisionRequest(decision="approved"),
                operator=operator,
                db=db,
            )
            allowed = main.mobile_history("ios-history-denied", 30, db)
            self.assertEqual(allowed[0]["approval_status"], "approved")

    def test_ios_and_android_ui_contracts_render_denied_status(self) -> None:
        self.assertEqual(main.PWA_VERSION, "1.2.1")
        self.assertEqual(main.LATEST_MOBILE_VERSION, "2.2.2")
        pwa = (main._core.PWA_DIR / "history-status.js").read_text(encoding="utf-8")
        sw = (main._core.PWA_DIR / "sw.js").read_text(encoding="utf-8")
        android = (
            main._core.BASE_DIR.parents[1]
            / "android/app/src/main/java/ru/rpo/mobile/ui/RpoUxApp.kt"
        ).read_text(encoding="utf-8")
        gradle = (main._core.BASE_DIR.parents[1] / "android/app/build.gradle.kts").read_text(encoding="utf-8")

        self.assertIn("Проведение запрещено", pwa)
        self.assertIn("history-denied", pwa)
        self.assertIn("rpo-pwa-shell-v1.2.1", sw)
        self.assertIn("history-status.js?v=20260901-1", sw)
        self.assertIn("HistoryFilter.DENIED", android)
        self.assertIn('"denied" -> "Проведение запрещено"', android)
        self.assertIn('versionName = "2.2.2"', gradle)


if __name__ == "__main__":
    unittest.main()

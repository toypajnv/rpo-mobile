from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select

from app import main
from app.database import Base, SessionLocal, engine
from app.models import MobileEvent
from app.schemas import EventCreate


class EventDedupeTests(unittest.TestCase):
    def setUp(self) -> None:
        Base.metadata.drop_all(engine)
        Base.metadata.create_all(engine)

    def tearDown(self) -> None:
        Base.metadata.drop_all(engine)

    def test_same_permit_stage_and_value_is_one_server_row(self) -> None:
        now = datetime.now(timezone.utc)
        with SessionLocal() as db:
            first = main._core.create_mobile_event(
                EventCreate(
                    client_event_id="retry-stage-first-0001",
                    device_id="device-1",
                    worker_name="Сергеев Сергей Владимирович",
                    structural_unit="ЦДПН-1",
                    permit_number="СН-040857",
                    field_key="AT",
                    stage_label="Начало подготовки",
                    event_time=now,
                    field_value="17.09.2026 09:47",
                    comment="",
                ),
                db,
            )
            second = main._core.create_mobile_event(
                EventCreate(
                    client_event_id="retry-stage-second-0002",
                    device_id="device-1",
                    worker_name="Сергеев Сергей Владимирович",
                    structural_unit="ЦДПН-1",
                    permit_number="СН-040857",
                    field_key="AT",
                    stage_label="Начало подготовки",
                    event_time=now + timedelta(seconds=35),
                    field_value="17.09.2026 09:47",
                    comment="повторное нажатие",
                ),
                db,
            )

            self.assertEqual(second.id, first.id)
            count = db.scalar(select(func.count()).select_from(MobileEvent))
            self.assertEqual(count, 1)

    def test_different_stage_value_remains_a_real_correction(self) -> None:
        now = datetime.now(timezone.utc)
        with SessionLocal() as db:
            first = main._core.create_mobile_event(
                EventCreate(
                    client_event_id="correction-first-0001",
                    device_id="device-1",
                    worker_name="Иванов И.И.",
                    structural_unit="ЦДПН-1",
                    permit_number="СН-040900",
                    field_key="AT",
                    stage_label="Начало подготовки",
                    event_time=now,
                    field_value="17.09.2026 09:47",
                    comment="",
                ),
                db,
            )
            second = main._core.create_mobile_event(
                EventCreate(
                    client_event_id="correction-second-0002",
                    device_id="device-1",
                    worker_name="Иванов И.И.",
                    structural_unit="ЦДПН-1",
                    permit_number="СН-040900",
                    field_key="AT",
                    stage_label="Начало подготовки",
                    event_time=now + timedelta(minutes=2),
                    field_value="17.09.2026 09:49",
                    comment="исправлено время",
                ),
                db,
            )

            self.assertNotEqual(second.id, first.id)
            count = db.scalar(select(func.count()).select_from(MobileEvent))
            self.assertEqual(count, 2)

    def test_cleanup_removes_only_non_current_duplicate(self) -> None:
        now = datetime.now(timezone.utc)
        with SessionLocal() as db:
            older = MobileEvent(
                client_event_id="legacy-duplicate-old-0001",
                device_id="device-1",
                worker_name="Авздяни И.Г.",
                structural_unit="ЦДПН-1",
                permit_number="СН-040853",
                field_key="BE",
                stage_label="Продление РПО",
                event_time=now,
                field_value="17.09.2026",
                comment="Работы выполнены не в полном объеме",
                approval_required=True,
                approval_status="pending",
                received_at=now,
            )
            db.add(older)
            db.flush()
            main._core._apply_event_to_record(db, older)
            db.flush()

            current = MobileEvent(
                client_event_id="legacy-duplicate-current-0002",
                device_id="device-1",
                worker_name="Авздяни И.Г.",
                structural_unit="ЦДПН-1",
                permit_number="СН-040853",
                field_key="BE",
                stage_label="Продление РПО",
                event_time=now + timedelta(seconds=25),
                field_value="17.09.2026",
                comment="",
                approval_required=True,
                approval_status="approved",
                received_at=now + timedelta(seconds=25),
            )
            db.add(current)
            db.flush()
            main._core._apply_event_to_record(db, current)
            db.commit()
            current_id = current.id

        removed = main._core.cleanup_redundant_stage_rows()
        self.assertEqual(removed, 1)

        with SessionLocal() as db:
            rows = list(db.scalars(select(MobileEvent)))
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0].id, current_id)
            # The useful comment is preserved on the canonical row.
            self.assertEqual(rows[0].comment, "Работы выполнены не в полном объеме")


if __name__ == "__main__":
    unittest.main()

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

    def _event(
        self,
        *,
        client_event_id: str,
        now: datetime,
        worker_name: str = "Сергеев Сергей Владимирович",
        structural_unit: str = "ЦДПН-1",
        permit_number: str = "СН-040857",
        field_key: str = "AT",
        stage_label: str = "Начало подготовки",
        field_value: str = "17.09.2026 09:47",
        comment: str = "",
    ) -> EventCreate:
        return EventCreate(
            client_event_id=client_event_id,
            device_id="device-1",
            worker_name=worker_name,
            structural_unit=structural_unit,
            permit_number=permit_number,
            field_key=field_key,
            stage_label=stage_label,
            event_time=now,
            field_value=field_value,
            comment=comment,
        )

    def test_same_logical_press_within_60_seconds_keeps_one_latest_row(self) -> None:
        now = datetime.now(timezone.utc)
        with SessionLocal() as db:
            first = main._core.create_mobile_event(
                self._event(
                    client_event_id="retry-stage-first-0001",
                    now=now,
                ),
                db,
            )
            first_id = first.id
            first_received_at = first.received_at

            second_time = now + timedelta(seconds=35)
            second = main._core.create_mobile_event(
                self._event(
                    client_event_id="retry-stage-second-0002",
                    now=second_time,
                    comment="повторное нажатие",
                ),
                db,
            )

            self.assertEqual(second.id, first_id)
            self.assertEqual(second.event_time, second_time)
            self.assertGreaterEqual(
                main._core.dt_utc(second.received_at),
                main._core.dt_utc(first_received_at),
            )
            self.assertEqual(second.comment, "повторное нажатие")
            count = db.scalar(select(func.count()).select_from(MobileEvent))
            self.assertEqual(count, 1)

    def test_same_stage_value_after_60_seconds_is_a_new_real_event(self) -> None:
        now = datetime.now(timezone.utc)
        with SessionLocal() as db:
            first = main._core.create_mobile_event(
                self._event(
                    client_event_id="later-repeat-first-0001",
                    now=now - timedelta(minutes=2),
                ),
                db,
            )
            first.received_at = now - timedelta(seconds=61)
            db.commit()

            second = main._core.create_mobile_event(
                self._event(
                    client_event_id="later-repeat-second-0002",
                    now=now,
                ),
                db,
            )

            self.assertNotEqual(second.id, first.id)
            count = db.scalar(select(func.count()).select_from(MobileEvent))
            self.assertEqual(count, 2)

    def test_different_worker_is_not_collapsed(self) -> None:
        now = datetime.now(timezone.utc)
        with SessionLocal() as db:
            first = main._core.create_mobile_event(
                self._event(
                    client_event_id="worker-first-0001",
                    now=now,
                    worker_name="Иванов И.И.",
                ),
                db,
            )
            second = main._core.create_mobile_event(
                self._event(
                    client_event_id="worker-second-0002",
                    now=now + timedelta(seconds=10),
                    worker_name="Петров П.П.",
                ),
                db,
            )

            self.assertNotEqual(second.id, first.id)
            count = db.scalar(select(func.count()).select_from(MobileEvent))
            self.assertEqual(count, 2)

    def test_different_stage_value_remains_a_real_correction(self) -> None:
        now = datetime.now(timezone.utc)
        with SessionLocal() as db:
            first = main._core.create_mobile_event(
                self._event(
                    client_event_id="correction-first-0001",
                    now=now,
                    worker_name="Иванов И.И.",
                    permit_number="СН-040900",
                ),
                db,
            )
            second = main._core.create_mobile_event(
                self._event(
                    client_event_id="correction-second-0002",
                    now=now + timedelta(minutes=2),
                    worker_name="Иванов И.И.",
                    permit_number="СН-040900",
                    field_value="17.09.2026 09:49",
                    comment="исправлено время",
                ),
                db,
            )

            self.assertNotEqual(second.id, first.id)
            count = db.scalar(select(func.count()).select_from(MobileEvent))
            self.assertEqual(count, 2)

    def test_duplicate_after_operator_decision_keeps_decision(self) -> None:
        now = datetime.now(timezone.utc)
        decided_at = now + timedelta(seconds=5)
        with SessionLocal() as db:
            first = main._core.create_mobile_event(
                self._event(
                    client_event_id="approved-first-0001",
                    now=now,
                    permit_number="СН-040853",
                    field_key="BE",
                    stage_label="Продление РПО",
                    field_value="17.09.2026",
                    comment="Работы выполнены не в полном объеме",
                ),
                db,
            )
            first.approval_status = "approved"
            first.approved_at = decided_at
            first.approved_by_id = 77
            main._core._apply_event_to_record(db, first)
            db.commit()

            second = main._core.create_mobile_event(
                self._event(
                    client_event_id="approved-second-0002",
                    now=now + timedelta(seconds=25),
                    permit_number="СН-040853",
                    field_key="BE",
                    stage_label="Продление РПО",
                    field_value="17.09.2026",
                    comment="Работы выполнены не в полном объеме",
                ),
                db,
            )

            self.assertEqual(second.id, first.id)
            self.assertEqual(second.approval_status, "approved")
            self.assertEqual(second.approved_at, decided_at)
            self.assertEqual(second.approved_by_id, 77)
            count = db.scalar(select(func.count()).select_from(MobileEvent))
            self.assertEqual(count, 1)

    def test_cleanup_removes_only_recent_non_current_duplicate(self) -> None:
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
            self.assertEqual(rows[0].comment, "Работы выполнены не в полном объеме")

    def test_cleanup_keeps_same_value_when_rows_are_more_than_60_seconds_apart(self) -> None:
        now = datetime.now(timezone.utc)
        with SessionLocal() as db:
            older = MobileEvent(
                client_event_id="legacy-real-old-0001",
                device_id="device-1",
                worker_name="Иванов И.И.",
                structural_unit="ЦДПН-1",
                permit_number="СН-041000",
                field_key="AT",
                stage_label="Начало подготовки",
                event_time=now - timedelta(minutes=3),
                field_value="17.09.2026 09:47",
                comment="",
                approval_required=True,
                approval_status="approved",
                received_at=now - timedelta(minutes=3),
            )
            db.add(older)
            db.flush()
            main._core._apply_event_to_record(db, older)

            current = MobileEvent(
                client_event_id="legacy-real-current-0002",
                device_id="device-1",
                worker_name="Иванов И.И.",
                structural_unit="ЦДПН-1",
                permit_number="СН-041000",
                field_key="AT",
                stage_label="Начало подготовки",
                event_time=now,
                field_value="17.09.2026 09:47",
                comment="",
                approval_required=True,
                approval_status="pending",
                received_at=now,
            )
            db.add(current)
            db.flush()
            main._core._apply_event_to_record(db, current)
            db.commit()

        removed = main._core.cleanup_redundant_stage_rows()
        self.assertEqual(removed, 0)

        with SessionLocal() as db:
            count = db.scalar(select(func.count()).select_from(MobileEvent))
            self.assertEqual(count, 2)


if __name__ == "__main__":
    unittest.main()

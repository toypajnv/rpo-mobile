from __future__ import annotations

import tempfile
import unittest

from openpyxl import Workbook

from app.database import Base, SessionLocal, engine
from app.ukz_registry import (
    UkzBlockRecord,
    find_ukz_block,
    parse_ukz_stoplist,
)


class UkzRegistryTests(unittest.TestCase):
    def setUp(self) -> None:
        Base.metadata.drop_all(engine)
        Base.metadata.create_all(engine)

    def tearDown(self) -> None:
        Base.metadata.drop_all(engine)

    def _xlsx(self, rows: list[list[object]]) -> str:
        workbook = Workbook()
        sheet = workbook.active
        sheet.title = "Стоп-лист"
        for row in rows:
            sheet.append(row)
        temp = tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False)
        temp.close()
        workbook.save(temp.name)
        workbook.close()
        self.addCleanup(lambda: __import__("pathlib").Path(temp.name).unlink(missing_ok=True))
        return temp.name

    def test_parser_finds_fio_video_marker_and_violation_description(self) -> None:
        path = self._xlsx([
            ["№", "ФИО работника", "Источник блокировки", "Описание нарушения"],
            [1, "Иванов Иван Иванович", "БДД", "Проход в опасную зону"],
            [2, "Петров Петр Петрович", "УКЗ", "Иное нарушение режима"],
        ])
        records, source_rows = parse_ukz_stoplist(path)
        self.assertEqual(source_rows, 2)
        self.assertEqual(len(records), 2)
        self.assertEqual(records[0].block_kind, "video")
        self.assertIn("Проход в опасную зону", records[0].violation_description)
        self.assertEqual(records[1].block_kind, "corporate")

    def test_sidorovich_inside_fio_does_not_create_false_video_block(self) -> None:
        path = self._xlsx([
            ["ФИО", "Инициатор", "Причина"],
            ["Смирнов Алексей Сидорович", "УКЗ", "Нарушение пропускного режима"],
        ])
        records, _ = parse_ukz_stoplist(path)
        self.assertEqual(records[0].block_kind, "corporate")

    def test_full_name_matches_initials_from_first_registry(self) -> None:
        with SessionLocal() as db:
            db.add(UkzBlockRecord(
                fio_raw="Иванов Иван Иванович",
                fio_normalized="ИВАНОВ ИВАН ИВАНОВИЧ",
                surname="ИВАНОВ",
                first_name="ИВАН",
                patronymic="ИВАНОВИЧ",
                block_kind="video",
                marker_text="БДД",
                violation_description="Нарушение по видеоаналитике",
                source_sheet="Лист1",
                source_row=2,
            ))
            db.commit()
            result = find_ukz_block(db, "Иванов И.И.")
        self.assertIsNotNone(result)
        self.assertEqual(result["kind"], "video")
        self.assertIn("видеоаналитике", result["description"])

    def test_missing_patronymic_can_match_unique_person(self) -> None:
        with SessionLocal() as db:
            db.add(UkzBlockRecord(
                fio_raw="Петров Петр Сергеевич",
                fio_normalized="ПЕТРОВ ПЕТР СЕРГЕЕВИЧ",
                surname="ПЕТРОВ",
                first_name="ПЕТР",
                patronymic="СЕРГЕЕВИЧ",
                block_kind="corporate",
                marker_text="УКЗ",
                violation_description="Нарушение режима",
                source_sheet="Лист1",
                source_row=3,
            ))
            db.commit()
            result = find_ukz_block(db, "Петров Петр")
        self.assertIsNotNone(result)
        self.assertEqual(result["kind"], "corporate")

    def test_ambiguous_initials_fail_closed_as_corporate_without_description(self) -> None:
        with SessionLocal() as db:
            for row, fio, first, patronymic, kind in [
                (2, "Иванов Иван Иванович", "ИВАН", "ИВАНОВИЧ", "video"),
                (3, "Иванов Илья Игоревич", "ИЛЬЯ", "ИГОРЕВИЧ", "corporate"),
            ]:
                db.add(UkzBlockRecord(
                    fio_raw=fio,
                    fio_normalized=fio.upper(),
                    surname="ИВАНОВ",
                    first_name=first,
                    patronymic=patronymic,
                    block_kind=kind,
                    marker_text="БДД" if kind == "video" else "УКЗ",
                    violation_description="Описание",
                    source_sheet="Лист1",
                    source_row=row,
                ))
            db.commit()
            result = find_ukz_block(db, "Иванов И.И.")
        self.assertIsNotNone(result)
        self.assertTrue(result["ambiguous"])
        self.assertEqual(result["kind"], "corporate")
        self.assertEqual(result["description"], "")


if __name__ == "__main__":
    unittest.main()

"""Pruebas de carga y calidad de datos."""

from __future__ import annotations

import unittest
from pathlib import Path

from src.data_quality import load_and_audit_csv


class DataQualityTests(unittest.TestCase):
    work_directory = Path(".test_work")

    @classmethod
    def setUpClass(cls) -> None:
        cls.work_directory.mkdir(exist_ok=True)

    def test_audit_preserves_records_and_reports_malformed_input(self) -> None:
        csv_text = """fecha_hora,equipo_id,rpm,vibracion_rms_mm_s,temperatura_c
2026-05-02 00:00:00,RED-001,0,1.5,50
2026-05-01 00:00:00,RED-001,100,2.0,45
2026-05-01 00:00:00,RED-001,100,2.0,45
bad-date,RED-001,-10,-1.0,-300
2026-05-03 00:00:00,RED-001,not-a-number,,inf
2026-05-01 00:00:00,RED-001,101,2.1,46
"""
        path = self.work_directory / "malformed_fixture.csv"
        try:
            path.write_text(csv_text, encoding="utf-8")
            result = load_and_audit_csv(path)
        finally:
            path.unlink(missing_ok=True)

        report = result.report
        self.assertEqual(report.rows_before, 6)
        self.assertEqual(report.rows_after, 6)
        self.assertEqual(report.missing_by_column["vibracion_rms_mm_s"], 1)
        self.assertEqual(report.invalid_timestamp_rows, [5])
        self.assertEqual(report.nonnumeric_rows["rpm"], [6])
        self.assertEqual(report.nonfinite_rows["temperatura_c"], [6])
        self.assertEqual(report.exact_duplicate_rows, [3, 4])
        self.assertEqual(report.duplicate_timestamp_equipment_rows, [3, 4, 7])
        self.assertEqual(report.negative_rpm_rows, [5])
        self.assertEqual(report.negative_vibration_rows, [5])
        self.assertEqual(report.below_absolute_zero_temperature_rows, [5])
        self.assertEqual(report.excluded_rows, [])
        self.assertEqual(result.data.iloc[0]["source_row"], 3)
        self.assertEqual(result.data.iloc[-1]["source_row"], 5)
        self.assertTrue(
            result.data.loc[
                result.data["source_row"] == 6, "temperatura_c"
            ].isna().all()
        )

    def test_missing_required_column_is_rejected(self) -> None:
        csv_text = "fecha_hora,equipo_id,rpm\n2026-05-01 00:00:00,RED-001,100\n"
        path = self.work_directory / "missing_column_fixture.csv"
        try:
            path.write_text(csv_text, encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "Faltan columnas obligatorias"):
                load_and_audit_csv(path)
        finally:
            path.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()

"""Pruebas de generación de gráficas."""

from __future__ import annotations

import unittest
from pathlib import Path

import pandas as pd

from src.visualization import create_plots


class VisualizationTests(unittest.TestCase):
    work_directory = Path(".test_work")

    @classmethod
    def setUpClass(cls) -> None:
        cls.work_directory.mkdir(exist_ok=True)

    def test_required_charts_are_written_for_each_equipment(self) -> None:
        data = pd.DataFrame(
            {
                "source_row": [2, 3, 4, 5],
                "fecha_hora": pd.date_range("2026-01-01", periods=4, freq="h"),
                "equipo_id": ["TEST/001"] * 4,
                "rpm": [500.0, 700.0, 900.0, 1_100.0],
                "vibracion_rms_mm_s": [1.5, 1.8, 2.1, 4.0],
                "temperatura_c": [48.0, 49.0, 50.0, 51.0],
            }
        )
        anomalies = data.loc[[3]].copy()

        paths: list[Path] = []
        try:
            paths = create_plots(data, anomalies, self.work_directory)
            names = sorted(path.name for path in paths)
            sizes = [Path(path).stat().st_size for path in paths]
        finally:
            for path in paths:
                path.unlink(missing_ok=True)

        self.assertEqual(
            names,
            [
                "rpm_vs_vibration_TEST_001.png",
                "vibration_over_time_TEST_001.png",
            ],
        )
        self.assertTrue(all(size > 0 for size in sizes))


if __name__ == "__main__":
    unittest.main()

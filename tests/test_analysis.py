"""Pruebas de los cálculos estadísticos."""

from __future__ import annotations

import unittest

import numpy as np
import pandas as pd

from src.analysis import analyze


class AnalysisTests(unittest.TestCase):
    def test_statistics_omit_only_missing_values_for_each_measurement(self) -> None:
        data = pd.DataFrame(
            {
                "source_row": [2, 3, 4],
                "fecha_hora": pd.date_range("2026-01-01", periods=3, freq="D"),
                "equipo_id": ["TEST-001"] * 3,
                "rpm": [100.0, 200.0, np.nan],
                "vibracion_rms_mm_s": [1.0, 2.0, 3.0],
                "temperatura_c": [10.0, 20.0, 30.0],
            }
        )

        result = analyze(data)
        statistics = result.descriptive_statistics.set_index("measurement")

        self.assertEqual(statistics.loc["rpm", "count"], 2)
        self.assertEqual(statistics.loc["vibracion_rms_mm_s", "count"], 3)
        self.assertAlmostEqual(statistics.loc["rpm", "mean"], 150.0)
        self.assertAlmostEqual(statistics.loc["rpm", "std"], 70.710678, places=5)

        correlations = result.correlations.set_index(
            ["first_measurement", "second_measurement", "method"]
        )
        key = ("rpm", "vibracion_rms_mm_s", "pearson")
        self.assertEqual(correlations.loc[key, "complete_pairs"], 2)
        self.assertAlmostEqual(correlations.loc[key, "correlation"], 1.0)
        spearman_key = ("rpm", "vibracion_rms_mm_s", "spearman")
        self.assertAlmostEqual(correlations.loc[spearman_key, "correlation"], 1.0)


if __name__ == "__main__":
    unittest.main()

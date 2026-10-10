"""Pruebas de detección de anomalías."""

from __future__ import annotations

import unittest

import numpy as np
import pandas as pd

from src.anomaly_detection import detect_vibration_anomalies


def _frame(rpm: list[float], vibration: list[float]) -> pd.DataFrame:
    count = len(rpm)
    return pd.DataFrame(
        {
            "source_row": np.arange(2, count + 2),
            "fecha_hora": pd.date_range("2026-01-01", periods=count, freq="h"),
            "equipo_id": ["TEST-001"] * count,
            "rpm": rpm,
            "vibracion_rms_mm_s": vibration,
            "temperatura_c": [50.0] * count,
        }
    )


class AnomalyDetectionTests(unittest.TestCase):
    def test_expected_high_rpm_vibration_is_not_flagged_but_peer_outlier_is(self) -> None:
        low_rpm = [480.0 + 2 * index for index in range(20)]
        high_rpm = [1480.0 + 2 * index for index in range(20)]
        low_vibration = [2.0 + 0.01 * ((index % 5) - 2) for index in range(20)]
        high_vibration = [4.0 + 0.01 * ((index % 5) - 2) for index in range(20)]
        low_vibration[10] = 7.0
        data = _frame(low_rpm + high_rpm, low_vibration + high_vibration)

        result = detect_vibration_anomalies(
            data, rpm_groups=2, minimum_group_size=10
        )

        self.assertEqual(result.anomalies["source_row"].tolist(), [12])
        self.assertNotIn(22, result.anomalies["source_row"].tolist())
        self.assertIn("no una falla confirmada", result.anomalies.iloc[0]["reason"])

    def test_zero_mad_uses_documented_standard_deviation_fallback(self) -> None:
        vibration = [2.0] * 20 + [9.0]
        data = _frame([1_000.0] * len(vibration), vibration)

        result = detect_vibration_anomalies(data, minimum_group_size=10)

        self.assertEqual(result.anomalies["source_row"].tolist(), [22])
        self.assertEqual(
            result.anomalies.iloc[0]["scale_method"],
            "desviación estándar muestral",
        )

    def test_missing_context_is_retained_as_unevaluated(self) -> None:
        data = _frame([500.0, np.nan], [2.0, 3.0])

        result = detect_vibration_anomalies(data, minimum_group_size=2)

        self.assertEqual(result.unevaluated_records["source_row"].tolist(), [2, 3])
        self.assertTrue(result.anomalies.empty)


if __name__ == "__main__":
    unittest.main()

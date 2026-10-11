"""Pruebas de los filtros de la interfaz."""

from __future__ import annotations

import unittest
from datetime import date

import pandas as pd

from app import filter_records


class DashboardTests(unittest.TestCase):
    def test_filters_equipment_and_inclusive_date_range(self) -> None:
        data = pd.DataFrame(
            {
                "source_row": [2, 3, 4],
                "fecha_hora": pd.to_datetime(
                    ["2026-01-01 06:00", "2026-01-02 06:00", "2026-01-02 12:00"]
                ),
                "equipo_id": ["A", "A", "B"],
            }
        )

        filtered = filter_records(data, ["A"], date(2026, 1, 2), date(2026, 1, 2))

        self.assertEqual(filtered["source_row"].tolist(), [3])


if __name__ == "__main__":
    unittest.main()

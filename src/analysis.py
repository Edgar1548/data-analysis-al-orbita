"""Análisis descriptivo de las mediciones."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from src.data_quality import load_and_audit_csv


MEASUREMENT_COLUMNS = ("rpm", "vibracion_rms_mm_s", "temperatura_c")


@dataclass(frozen=True)
class AnalysisResult:
    """Tablas generadas por el análisis."""

    descriptive_statistics: pd.DataFrame
    correlations: pd.DataFrame
    rpm_group_summary: pd.DataFrame
    weekly_summary: pd.DataFrame
    time_trends: pd.DataFrame


def _descriptive_statistics(data: pd.DataFrame) -> pd.DataFrame:
    """Calcula estadísticas omitiendo datos faltantes."""

    statistics = data.loc[:, list(MEASUREMENT_COLUMNS)].agg(
        ["count", "mean", "min", "max", "std"]
    )
    return statistics.T.rename_axis("measurement").reset_index()


def _correlations(data: pd.DataFrame) -> pd.DataFrame:
    """Calcula correlaciones con pares completos."""

    relationships = (
        ("rpm", "vibracion_rms_mm_s"),
        ("temperatura_c", "vibracion_rms_mm_s"),
    )
    rows: list[dict[str, object]] = []
    for first, second in relationships:
        complete = data[[first, second]].dropna()
        for method in ("pearson", "spearman"):
            if len(complete) < 2:
                value = np.nan
            elif method == "spearman":
                # Spearman equivale a Pearson aplicado a rangos.
                value = complete[first].rank(method="average").corr(
                    complete[second].rank(method="average"), method="pearson"
                )
            else:
                value = complete[first].corr(complete[second], method="pearson")
            rows.append(
                {
                    "first_measurement": first,
                    "second_measurement": second,
                    "method": method,
                    "complete_pairs": len(complete),
                    "correlation": value,
                }
            )
    return pd.DataFrame(rows)


def _rpm_group_summary(data: pd.DataFrame) -> pd.DataFrame:
    """Resume la vibración en cuatro grupos de RPM."""

    usable = data.dropna(subset=["rpm"]).copy()
    if usable.empty:
        return pd.DataFrame(
            columns=(
                "rpm_group",
                "records",
                "rpm_min",
                "rpm_max",
                "vibration_count",
                "vibration_mean",
                "vibration_median",
                "vibration_std",
            )
        )

    usable["rpm_group"] = pd.qcut(usable["rpm"], q=4, duplicates="drop")
    summary = (
        usable.groupby("rpm_group", observed=True)
        .agg(
            records=("source_row", "size"),
            rpm_min=("rpm", "min"),
            rpm_max=("rpm", "max"),
            vibration_count=("vibracion_rms_mm_s", "count"),
            vibration_mean=("vibracion_rms_mm_s", "mean"),
            vibration_median=("vibracion_rms_mm_s", "median"),
            vibration_std=("vibracion_rms_mm_s", "std"),
        )
        .reset_index()
    )
    summary["rpm_group"] = summary["rpm_group"].astype(str)
    return summary


def _weekly_summary(data: pd.DataFrame) -> pd.DataFrame:
    """Resume las mediciones por semana y equipo."""

    usable = data.dropna(subset=["fecha_hora", "equipo_id"])
    return (
        usable.groupby(
            [
                "equipo_id",
                pd.Grouper(key="fecha_hora", freq="7D", origin="start_day"),
            ],
            dropna=False,
        )
        .agg(
            records=("source_row", "size"),
            rpm_count=("rpm", "count"),
            rpm_mean=("rpm", "mean"),
            vibration_count=("vibracion_rms_mm_s", "count"),
            vibration_mean=("vibracion_rms_mm_s", "mean"),
            temperature_count=("temperatura_c", "count"),
            temperature_mean=("temperatura_c", "mean"),
        )
        .reset_index()
        .rename(columns={"fecha_hora": "period_start"})
    )


def _time_trends(data: pd.DataFrame) -> pd.DataFrame:
    """Estima el cambio lineal por cada 30 días."""

    rows: list[dict[str, object]] = []
    usable = data.dropna(subset=["fecha_hora", "equipo_id"])
    for equipment_id, equipment_data in usable.groupby("equipo_id"):
        for measurement in MEASUREMENT_COLUMNS:
            complete = equipment_data.dropna(subset=[measurement])
            if len(complete) < 2:
                slope = np.nan
            else:
                elapsed_days = (
                    complete["fecha_hora"] - complete["fecha_hora"].min()
                ).dt.total_seconds() / 86_400
                slope = float(
                    np.polyfit(
                        elapsed_days.to_numpy(dtype=float),
                        complete[measurement].to_numpy(dtype=float),
                        deg=1,
                    )[0]
                    * 30
                )
            rows.append(
                {
                    "equipo_id": equipment_id,
                    "measurement": measurement,
                    "complete_records": len(complete),
                    "linear_change_per_30_days": slope,
                }
            )
    return pd.DataFrame(rows)


def analyze(data: pd.DataFrame) -> AnalysisResult:
    """Genera las tablas del análisis."""

    return AnalysisResult(
        descriptive_statistics=_descriptive_statistics(data),
        correlations=_correlations(data),
        rpm_group_summary=_rpm_group_summary(data),
        weekly_summary=_weekly_summary(data),
        time_trends=_time_trends(data),
    )


def save_analysis(result: AnalysisResult, output_directory: str | Path) -> None:
    """Guarda las tablas en archivos CSV."""

    output_path = Path(output_directory)
    output_path.mkdir(parents=True, exist_ok=True)
    for name, table in (
        ("descriptive_statistics", result.descriptive_statistics),
        ("correlations", result.correlations),
        ("rpm_group_summary", result.rpm_group_summary),
        ("weekly_summary", result.weekly_summary),
        ("time_trends", result.time_trends),
    ):
        table.to_csv(output_path / f"{name}.csv", index=False)


def main() -> None:
    """Ejecuta y guarda el análisis."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("csv_path", nargs="?", default="MBC_Prueba.csv")
    parser.add_argument("--output", default="outputs")
    args = parser.parse_args()

    audited = load_and_audit_csv(args.csv_path)
    result = analyze(audited.data)
    save_analysis(result, args.output)
    print(result.descriptive_statistics.to_string(index=False))
    print("\nCorrelaciones por pares")
    print(result.correlations.to_string(index=False))


if __name__ == "__main__":
    main()

"""Genera las gráficas estáticas."""

from __future__ import annotations

import argparse
import re
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

from src.anomaly_detection import (
    detect_vibration_anomalies,
    save_anomaly_results,
)
from src.data_quality import load_and_audit_csv


def _safe_filename(value: object) -> str:
    """Adapta el identificador para usarlo en un archivo."""

    safe = re.sub(r"[^A-Za-z0-9._-]+", "_", str(value)).strip("._")
    return safe or "unknown_equipment"


def _equipment_anomalies(
    anomalies: pd.DataFrame, equipment_id: object
) -> pd.DataFrame:
    """Selecciona las anomalías de un equipo."""

    if anomalies.empty:
        return anomalies.copy()
    return anomalies.loc[anomalies["equipo_id"] == equipment_id].copy()


def _plot_vibration_over_time(
    equipment_data: pd.DataFrame,
    equipment_anomalies: pd.DataFrame,
    equipment_id: object,
    destination: Path,
) -> None:
    """Grafica la vibración a lo largo del tiempo."""

    valid = equipment_data.dropna(subset=["fecha_hora", "vibracion_rms_mm_s"])
    figure, axis = plt.subplots(figsize=(12, 5.5))
    axis.plot(
        valid["fecha_hora"],
        valid["vibracion_rms_mm_s"],
        color="#286090",
        linewidth=1.1,
        marker="o",
        markersize=2.8,
        label="Medición de vibración",
    )
    if not equipment_anomalies.empty:
        axis.scatter(
            equipment_anomalies["fecha_hora"],
            equipment_anomalies["vibracion_rms_mm_s"],
            color="#c9302c",
            edgecolor="black",
            linewidth=0.5,
            marker="X",
            s=65,
            zorder=3,
            label="Anomalía contextual",
        )
    axis.set_title(f"Vibración a lo largo del tiempo: equipo {equipment_id}")
    axis.set_xlabel("Fecha y hora (zona horaria no informada)")
    axis.set_ylabel("Vibración (mm/s RMS)")
    axis.grid(alpha=0.25)
    axis.legend()
    figure.autofmt_xdate()
    figure.tight_layout()
    figure.savefig(destination, dpi=150, bbox_inches="tight")
    plt.close(figure)


def _plot_rpm_vs_vibration(
    equipment_data: pd.DataFrame,
    equipment_anomalies: pd.DataFrame,
    equipment_id: object,
    destination: Path,
) -> None:
    """Grafica las RPM frente a la vibración."""

    valid = equipment_data.dropna(subset=["rpm", "vibracion_rms_mm_s"])
    figure, axis = plt.subplots(figsize=(8, 6))
    axis.scatter(
        valid["rpm"],
        valid["vibracion_rms_mm_s"],
        color="#286090",
        alpha=0.7,
        s=28,
        label="Medición",
    )
    if not equipment_anomalies.empty:
        axis.scatter(
            equipment_anomalies["rpm"],
            equipment_anomalies["vibracion_rms_mm_s"],
            color="#c9302c",
            edgecolor="black",
            linewidth=0.5,
            marker="X",
            s=75,
            zorder=3,
            label="Anomalía contextual",
        )
    axis.set_title(f"RPM frente a vibración: equipo {equipment_id}")
    axis.set_xlabel("Velocidad de operación (RPM)")
    axis.set_ylabel("Vibración (mm/s RMS)")
    axis.grid(alpha=0.25)
    axis.legend()
    figure.tight_layout()
    figure.savefig(destination, dpi=150, bbox_inches="tight")
    plt.close(figure)


def create_plots(
    data: pd.DataFrame,
    anomalies: pd.DataFrame,
    output_directory: str | Path,
) -> list[Path]:
    """Guarda las gráficas y devuelve sus rutas."""

    output_path = Path(output_directory)
    output_path.mkdir(parents=True, exist_ok=True)
    created: list[Path] = []

    equipment_values = data["equipo_id"].dropna().drop_duplicates().tolist()
    for equipment_id in equipment_values:
        equipment_data = data.loc[data["equipo_id"] == equipment_id]
        flagged = _equipment_anomalies(anomalies, equipment_id)
        filename_id = _safe_filename(equipment_id)

        time_path = output_path / f"vibration_over_time_{filename_id}.png"
        _plot_vibration_over_time(
            equipment_data, flagged, equipment_id, time_path
        )
        created.append(time_path)

        scatter_path = output_path / f"rpm_vs_vibration_{filename_id}.png"
        _plot_rpm_vs_vibration(
            equipment_data, flagged, equipment_id, scatter_path
        )
        created.append(scatter_path)

    return created


def main() -> None:
    """Procesa los datos y genera las gráficas."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("csv_path", nargs="?", default="MBC_Prueba.csv")
    parser.add_argument("--output", default="outputs")
    args = parser.parse_args()

    audited = load_and_audit_csv(args.csv_path)
    anomaly_result = detect_vibration_anomalies(audited.data)
    save_anomaly_results(anomaly_result, args.output)
    paths = create_plots(audited.data, anomaly_result.anomalies, args.output)
    for path in paths:
        print(path)


if __name__ == "__main__":
    main()

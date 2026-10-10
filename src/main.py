"""Ejecuta el análisis completo."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from src.analysis import analyze, save_analysis
from src.anomaly_detection import detect_vibration_anomalies, save_anomaly_results
from src.data_quality import load_and_audit_csv
from src.visualization import create_plots


def run_pipeline(csv_path: str | Path, output_directory: str | Path) -> None:
    """Procesa el CSV y genera todos los resultados."""

    output_path = Path(output_directory)
    output_path.mkdir(parents=True, exist_ok=True)

    audit = load_and_audit_csv(csv_path)
    (output_path / "quality_report.json").write_text(
        json.dumps(audit.report.to_dict(), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    analysis = analyze(audit.data)
    save_analysis(analysis, output_path)

    anomaly_result = detect_vibration_anomalies(audit.data)
    save_anomaly_results(anomaly_result, output_path)
    plot_paths = create_plots(audit.data, anomaly_result.anomalies, output_path)

    print(f"Registros procesados: {audit.report.rows_after}")
    print(f"Registros marcados: {len(anomaly_result.anomalies)}")
    print(f"Registros sin evaluar: {len(anomaly_result.unevaluated_records)}")
    print(f"Directorio de resultados: {output_path.resolve()}")
    for plot_path in plot_paths:
        print(f"Gráfica: {plot_path}")


def main() -> None:
    """Lee los argumentos y ejecuta el análisis."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("csv_path", nargs="?", default="MBC_Prueba.csv")
    parser.add_argument("--output", default="outputs")
    args = parser.parse_args()
    run_pipeline(args.csv_path, args.output)


if __name__ == "__main__":
    main()

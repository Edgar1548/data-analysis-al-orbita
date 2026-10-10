"""Detecta vibraciones inusuales según su contexto de RPM."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from src.data_quality import load_and_audit_csv


DEFAULT_RPM_GROUPS = 8
DEFAULT_MINIMUM_GROUP_SIZE = 15
DEFAULT_SCORE_LIMIT = 3.5
NORMAL_MAD_SCALE_FACTOR = 0.6744897501960817


@dataclass(frozen=True)
class AnomalyResult:
    """Anomalías, líneas base y registros sin evaluar."""

    anomalies: pd.DataFrame
    band_baselines: pd.DataFrame
    unevaluated_records: pd.DataFrame


def _assign_rpm_groups(context: pd.DataFrame, requested_groups: int) -> pd.Series:
    """Asigna grupos de RPM por cuantiles."""

    if context["rpm"].nunique() == 1:
        return pd.Series("todas las RPM", index=context.index, dtype="string")
    group_count = min(requested_groups, len(context), context["rpm"].nunique())
    return pd.qcut(context["rpm"], q=group_count, duplicates="drop")


def detect_vibration_anomalies(
    data: pd.DataFrame,
    *,
    rpm_groups: int = DEFAULT_RPM_GROUPS,
    minimum_group_size: int = DEFAULT_MINIMUM_GROUP_SIZE,
    score_limit: float = DEFAULT_SCORE_LIMIT,
) -> AnomalyResult:
    """Detecta vibraciones inusuales entre RPM comparables."""

    if rpm_groups < 1:
        raise ValueError("rpm_groups debe ser al menos 1")
    if minimum_group_size < 2:
        raise ValueError("minimum_group_size debe ser al menos 2")
    if score_limit <= 0:
        raise ValueError("score_limit debe ser positivo")

    required = {
        "source_row",
        "fecha_hora",
        "equipo_id",
        "rpm",
        "vibracion_rms_mm_s",
        "temperatura_c",
    }
    missing = sorted(required.difference(data.columns))
    if missing:
        raise ValueError(f"Faltan columnas para el análisis: {', '.join(missing)}")

    context_mask = data["rpm"].notna() & data["vibracion_rms_mm_s"].notna()
    context = data.loc[context_mask].copy()
    unevaluated = data.loc[~context_mask].copy()
    unevaluated["reason"] = np.where(
        unevaluated["rpm"].isna() & unevaluated["vibracion_rms_mm_s"].isna(),
        "Faltan RPM y vibración",
        np.where(
            unevaluated["rpm"].isna(),
            "Faltan RPM",
            "Falta vibración",
        ),
    )

    anomaly_rows: list[dict[str, object]] = []
    baseline_rows: list[dict[str, object]] = []
    if not context.empty:
        context["rpm_band"] = _assign_rpm_groups(context, rpm_groups)

    for rpm_band, group in context.groupby("rpm_band", observed=True):
        band_label = str(rpm_band)
        vibration = group["vibracion_rms_mm_s"].astype(float)
        median = float(vibration.median())
        mad = float((vibration - median).abs().median())
        scale_method = "MAD"
        scale = mad / NORMAL_MAD_SCALE_FACTOR
        evaluable = len(group) >= minimum_group_size

        if mad == 0:
            scale = float(vibration.std(ddof=1))
            scale_method = "desviación estándar muestral"
        if not np.isfinite(scale) or scale == 0:
            evaluable = False
            scale_method = "sin dispersión"

        lower_threshold = median - score_limit * scale if evaluable else np.nan
        upper_threshold = median + score_limit * scale if evaluable else np.nan
        baseline_rows.append(
            {
                "rpm_band": band_label,
                "context_records": len(group),
                "rpm_min": float(group["rpm"].min()),
                "rpm_max": float(group["rpm"].max()),
                "vibration_median": median,
                "vibration_mad": mad,
                "scale": scale,
                "scale_method": scale_method,
                "score_limit": score_limit,
                "lower_threshold": lower_threshold,
                "upper_threshold": upper_threshold,
                "evaluable": evaluable,
            }
        )

        if not evaluable:
            reason = (
                f"El grupo RPM {band_label} no se evaluó: n={len(group)}, "
                f"mínimo={minimum_group_size}, método={scale_method}."
            )
            group_unevaluated = group.copy()
            group_unevaluated["reason"] = reason
            unevaluated = pd.concat([unevaluated, group_unevaluated], ignore_index=True)
            continue

        scores = (vibration - median) / scale
        flagged = group.loc[scores.abs() > score_limit]
        for index, record in flagged.iterrows():
            score = float(scores.loc[index])
            direction = "supera" if score > 0 else "está por debajo de"
            threshold = upper_threshold if score > 0 else lower_threshold
            anomaly_rows.append(
                {
                    "source_row": int(record["source_row"]),
                    "fecha_hora": record["fecha_hora"],
                    "equipo_id": record["equipo_id"],
                    "rpm": float(record["rpm"]),
                    "vibracion_rms_mm_s": float(record["vibracion_rms_mm_s"]),
                    "temperatura_c": record["temperatura_c"],
                    "rpm_band": band_label,
                    "context_records": len(group),
                    "context_vibration_median": median,
                    "context_vibration_mad": mad,
                    "scale_method": scale_method,
                    "anomaly_score": score,
                    "score_limit": score_limit,
                    "lower_threshold": lower_threshold,
                    "upper_threshold": upper_threshold,
                    "rule": f"puntaje contextual absoluto > {score_limit:g}",
                    "reason": (
                        f"La vibración de {record['vibracion_rms_mm_s']:.3f} mm/s RMS "
                        f"{direction} el umbral {threshold:.3f} del grupo RPM "
                        f"{band_label} (mediana {median:.3f}, n={len(group)}). "
                        "Es una señal estadística, no una falla confirmada."
                    ),
                }
            )

    anomaly_columns = (
        "source_row",
        "fecha_hora",
        "equipo_id",
        "rpm",
        "vibracion_rms_mm_s",
        "temperatura_c",
        "rpm_band",
        "context_records",
        "context_vibration_median",
        "context_vibration_mad",
        "scale_method",
        "anomaly_score",
        "score_limit",
        "lower_threshold",
        "upper_threshold",
        "rule",
        "reason",
    )
    anomalies = pd.DataFrame(anomaly_rows, columns=anomaly_columns)
    if not anomalies.empty:
        anomalies = anomalies.sort_values(
            ["fecha_hora", "source_row"], kind="stable"
        ).reset_index(drop=True)

    baselines = pd.DataFrame(baseline_rows)
    unevaluated = unevaluated.sort_values("source_row", kind="stable").reset_index(
        drop=True
    )
    return AnomalyResult(anomalies, baselines, unevaluated)


def save_anomaly_results(result: AnomalyResult, output_directory: str | Path) -> None:
    """Guarda anomalías y cobertura en archivos CSV."""

    output_path = Path(output_directory)
    output_path.mkdir(parents=True, exist_ok=True)
    result.anomalies.to_csv(output_path / "anomalies.csv", index=False)
    result.band_baselines.to_csv(output_path / "anomaly_band_baselines.csv", index=False)
    result.unevaluated_records.to_csv(
        output_path / "anomaly_unevaluated_records.csv", index=False
    )


def main() -> None:
    """Ejecuta la detección de anomalías."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("csv_path", nargs="?", default="MBC_Prueba.csv")
    parser.add_argument("--output", default="outputs")
    args = parser.parse_args()

    audited = load_and_audit_csv(args.csv_path)
    result = detect_vibration_anomalies(audited.data)
    save_anomaly_results(result, args.output)
    print(result.anomalies.to_string(index=False))
    print(f"\nRegistros marcados: {len(result.anomalies)}")
    print(f"Registros sin evaluar: {len(result.unevaluated_records)}")


if __name__ == "__main__":
    main()

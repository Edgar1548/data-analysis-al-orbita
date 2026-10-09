"""Carga y audita el archivo de mediciones."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np
import pandas as pd


REQUIRED_COLUMNS = (
    "fecha_hora",
    "equipo_id",
    "rpm",
    "vibracion_rms_mm_s",
    "temperatura_c",
)
NUMERIC_COLUMNS = ("rpm", "vibracion_rms_mm_s", "temperatura_c")
TIMESTAMP_FORMAT = "%Y-%m-%d %H:%M:%S"


@dataclass(frozen=True)
class QualityReport:
    """Resultados de la auditoría del CSV."""

    rows_before: int
    rows_after: int
    missing_by_column: dict[str, int]
    invalid_timestamp_rows: list[int]
    nonnumeric_rows: dict[str, list[int]]
    nonfinite_rows: dict[str, list[int]]
    exact_duplicate_rows: list[int]
    duplicate_timestamp_equipment_rows: list[int]
    negative_rpm_rows: list[int]
    negative_vibration_rows: list[int]
    below_absolute_zero_temperature_rows: list[int]
    excluded_rows: list[int]
    decisions: list[str]

    def to_dict(self) -> dict[str, object]:
        """Convierte el reporte en un diccionario."""

        return asdict(self)


@dataclass(frozen=True)
class AuditResult:
    """Datos procesados y reporte de calidad."""

    data: pd.DataFrame
    report: QualityReport


def _source_rows(mask: pd.Series, source_rows: pd.Series) -> list[int]:
    """Obtiene las líneas del CSV que cumplen la condición."""

    return source_rows.loc[mask].astype(int).tolist()


def load_and_audit_csv(path: str | Path) -> AuditResult:
    """Carga, audita y ordena el CSV sin eliminar registros."""

    csv_path = Path(path)
    raw = pd.read_csv(csv_path, dtype=str, keep_default_na=False, encoding="utf-8-sig")

    missing_columns = [column for column in REQUIRED_COLUMNS if column not in raw.columns]
    if missing_columns:
        names = ", ".join(missing_columns)
        raise ValueError(f"Faltan columnas obligatorias: {names}")

    raw = raw.loc[:, list(REQUIRED_COLUMNS)].copy()
    raw.insert(0, "source_row", np.arange(2, len(raw) + 2, dtype=int))
    source_rows = raw["source_row"]

    stripped = raw.loc[:, list(REQUIRED_COLUMNS)].apply(
        lambda column: column.str.strip()
    )
    missing_masks = {column: stripped[column].eq("") for column in REQUIRED_COLUMNS}
    missing_by_column = {
        column: int(mask.sum()) for column, mask in missing_masks.items()
    }

    exact_duplicate_mask = stripped.duplicated(keep=False)
    valid_key_mask = ~missing_masks["fecha_hora"] & ~missing_masks["equipo_id"]
    duplicate_key_mask = (
        stripped.duplicated(subset=["fecha_hora", "equipo_id"], keep=False)
        & valid_key_mask
    )

    parsed_timestamp = pd.to_datetime(
        stripped["fecha_hora"], format=TIMESTAMP_FORMAT, errors="coerce"
    )
    invalid_timestamp_mask = ~missing_masks["fecha_hora"] & parsed_timestamp.isna()

    parsed_numeric: dict[str, pd.Series] = {}
    nonnumeric_rows: dict[str, list[int]] = {}
    nonfinite_rows: dict[str, list[int]] = {}
    for column in NUMERIC_COLUMNS:
        parsed = pd.to_numeric(stripped[column].replace("", pd.NA), errors="coerce")
        nonnumeric_mask = ~missing_masks[column] & parsed.isna()
        finite_mask = pd.Series(
            np.isfinite(parsed.astype(float)), index=parsed.index, dtype=bool
        )
        nonfinite_mask = ~missing_masks[column] & parsed.notna() & ~finite_mask
        nonnumeric_rows[column] = _source_rows(nonnumeric_mask, source_rows)
        nonfinite_rows[column] = _source_rows(nonfinite_mask, source_rows)
        parsed_numeric[column] = parsed.mask(nonfinite_mask, pd.NA)

    cleaned = pd.DataFrame(
        {
            "source_row": source_rows,
            "fecha_hora": parsed_timestamp,
            "equipo_id": stripped["equipo_id"].replace("", pd.NA),
            **parsed_numeric,
        }
    )
    cleaned = cleaned.sort_values(
        ["fecha_hora", "source_row"], kind="stable", na_position="last"
    ).reset_index(drop=True)

    report = QualityReport(
        rows_before=len(raw),
        rows_after=len(cleaned),
        missing_by_column=missing_by_column,
        invalid_timestamp_rows=_source_rows(invalid_timestamp_mask, source_rows),
        nonnumeric_rows=nonnumeric_rows,
        nonfinite_rows=nonfinite_rows,
        exact_duplicate_rows=_source_rows(exact_duplicate_mask, source_rows),
        duplicate_timestamp_equipment_rows=_source_rows(
            duplicate_key_mask, source_rows
        ),
        negative_rpm_rows=_source_rows(parsed_numeric["rpm"] < 0, source_rows),
        negative_vibration_rows=_source_rows(
            parsed_numeric["vibracion_rms_mm_s"] < 0, source_rows
        ),
        below_absolute_zero_temperature_rows=_source_rows(
            parsed_numeric["temperatura_c"] < -273.15, source_rows
        ),
        excluded_rows=[],
        decisions=[
            "Se conservaron todos los registros.",
            "No se imputaron mediciones faltantes o inválidas.",
            "Los valores inválidos se convirtieron en datos faltantes.",
            "Los registros válidos se ordenaron cronológicamente.",
            "Las RPM iguales a cero se aceptaron como válidas.",
            "Las RPM y vibraciones negativas se marcaron como sospechosas.",
        ],
    )
    return AuditResult(data=cleaned, report=report)


def main() -> None:
    """Imprime el reporte de calidad en formato JSON."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("csv_path", nargs="?", default="MBC_Prueba.csv")
    args = parser.parse_args()
    result = load_and_audit_csv(args.csv_path)
    print(json.dumps(result.report.to_dict(), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()

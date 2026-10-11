"""Interfaz interactiva para explorar las mediciones del equipo industrial."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from src.anomaly_detection import detect_vibration_anomalies
from src.data_quality import load_and_audit_csv


DATA_PATH = Path(__file__).with_name("MBC_Prueba.csv")


@st.cache_data(show_spinner=False)
def load_dashboard_data(path: str, modified_time: float):
    """Carga y analiza el archivo mientras no cambie."""

    del modified_time
    audit = load_and_audit_csv(path)
    anomaly_result = detect_vibration_anomalies(audit.data)
    return audit.data, audit.report.to_dict(), anomaly_result


def filter_records(
    data: pd.DataFrame,
    equipment_ids: list[str],
    start_date: date,
    end_date: date,
) -> pd.DataFrame:
    """Filtra la vista sin recalcular las anomalías."""

    timestamp_dates = data["fecha_hora"].dt.date
    mask = (
        data["equipo_id"].isin(equipment_ids)
        & timestamp_dates.ge(start_date)
        & timestamp_dates.le(end_date)
    )
    return data.loc[mask].copy()


def add_anomaly_trace(
    figure: go.Figure,
    anomalies: pd.DataFrame,
    *,
    x: str,
) -> None:
    """Agrega los marcadores de anomalías."""

    if anomalies.empty:
        return
    figure.add_trace(
        go.Scatter(
            x=anomalies[x],
            y=anomalies["vibracion_rms_mm_s"],
            mode="markers",
            name="Anomalía contextual",
            marker={"color": "#C62828", "size": 12, "symbol": "x"},
            customdata=anomalies[
                ["source_row", "rpm", "temperatura_c", "anomaly_score"]
            ],
            hovertemplate=(
                "Línea CSV: %{customdata[0]}<br>"
                "RPM: %{customdata[1]:.0f}<br>"
                "Vibración: %{y:.3f} mm/s RMS<br>"
                "Temperatura: %{customdata[2]:.1f} °C<br>"
                "Puntaje: %{customdata[3]:.2f}<extra></extra>"
            ),
        )
    )


def main() -> None:
    """Muestra la aplicación Streamlit."""

    st.set_page_config(
        page_title="Análisis de equipo industrial",
        page_icon="📈",
        layout="wide",
    )
    st.title("Análisis de funcionamiento del equipo")
    st.caption(
        "Exploración de RPM, vibración y temperatura. Las anomalías son señales "
        "estadísticas para investigar, no fallas mecánicas confirmadas."
    )

    if not DATA_PATH.exists():
        st.error(f"No se encontró el archivo requerido: {DATA_PATH.name}")
        st.stop()

    data, quality_report, anomaly_result = load_dashboard_data(
        str(DATA_PATH), DATA_PATH.stat().st_mtime
    )
    anomalies = anomaly_result.anomalies

    valid_timestamps = data["fecha_hora"].dropna()
    minimum_date = valid_timestamps.min().date()
    maximum_date = valid_timestamps.max().date()
    equipment_options = data["equipo_id"].dropna().drop_duplicates().tolist()

    with st.sidebar:
        st.header("Filtros")
        selected_equipment = st.multiselect(
            "Equipos",
            equipment_options,
            default=equipment_options,
            help="Los filtros cambian la visualización, no recalculan la línea base.",
        )
        selected_dates = st.date_input(
            "Rango de fechas",
            value=(minimum_date, maximum_date),
            min_value=minimum_date,
            max_value=maximum_date,
        )
        st.divider()
        st.caption(f"Fuente: {DATA_PATH.name}")

    if isinstance(selected_dates, tuple) and len(selected_dates) == 2:
        start_date, end_date = selected_dates
    else:
        start_date = end_date = selected_dates

    filtered = filter_records(data, selected_equipment, start_date, end_date)
    filtered_source_rows = set(filtered["source_row"].tolist())
    filtered_anomalies = anomalies.loc[
        anomalies["source_row"].isin(filtered_source_rows)
    ].copy()
    filtered_unevaluated = anomaly_result.unevaluated_records.loc[
        anomaly_result.unevaluated_records["source_row"].isin(filtered_source_rows)
    ]

    if filtered.empty:
        st.warning("No hay registros para los filtros seleccionados.")
        st.stop()

    metric_columns = st.columns(4)
    metric_columns[0].metric("Registros", len(filtered))
    metric_columns[1].metric(
        "Vibraciones válidas", int(filtered["vibracion_rms_mm_s"].notna().sum())
    )
    metric_columns[2].metric("Anomalías", len(filtered_anomalies))
    metric_columns[3].metric("Sin evaluar", len(filtered_unevaluated))

    st.info(
        "**Conclusión principal:** la vibración aumenta normalmente con las RPM, "
        "pero se identificó un período inusual entre el 7 y el 13 de junio. "
        "Los datos justifican una revisión operativa; no demuestran una falla mecánica."
    )

    (
        overview_tab,
        conclusions_tab,
        time_tab,
        relation_tab,
        anomalies_tab,
        method_tab,
    ) = st.tabs(
        [
            "Resumen",
            "Conclusiones",
            "Evolución",
            "RPM y vibración",
            "Anomalías",
            "Método",
        ]
    )

    with overview_tab:
        st.subheader("Estadísticas descriptivas")
        summary = (
            filtered[["rpm", "vibracion_rms_mm_s", "temperatura_c"]]
            .agg(["count", "mean", "min", "max", "std"])
            .T.rename(
                columns={
                    "count": "Cantidad válida",
                    "mean": "Promedio",
                    "min": "Mínimo",
                    "max": "Máximo",
                    "std": "Desviación estándar",
                }
            )
        )
        summary.index = ["RPM", "Vibración (mm/s RMS)", "Temperatura (°C)"]
        st.dataframe(summary.style.format(precision=3), width="stretch")

        with st.expander("Calidad de los datos"):
            st.write(
                "El reporte corresponde al archivo completo; los filtros solo afectan "
                "las vistas de esta página."
            )
            st.json(quality_report)

    with conclusions_tab:
        st.subheader("Conclusiones del análisis completo")
        st.markdown(
            """
1. **La velocidad de operación explica parte importante de la vibración.**  
   La relación RPM–vibración es positiva: Pearson = 0,759 y Spearman = 0,811.
   Por eso no es apropiado evaluar todas las vibraciones con un único límite
   estadístico sin considerar las RPM.

2. **Existe un período claramente inusual entre el 7 y el 13 de junio.**  
   De las 21 mediciones señaladas, 18 se concentran en esos siete días. Además,
   la semana que comienza el 5 de junio tiene la vibración media más alta
   (3,055 mm/s RMS) pese a registrar cerca de 800 RPM en promedio.

3. **Temperatura y vibración se mueven en la misma dirección, pero no se puede
   afirmar causalidad.**  
   Sus correlaciones son Pearson = 0,691 y Spearman = 0,753. RPM, carga, estado
   operativo u otras variables no registradas podrían influir en ambas.

4. **La calidad general del archivo permite analizarlo sin eliminar registros.**  
   Se conservaron los 240 registros. Hay dos RPM y tres vibraciones faltantes;
   esos cinco casos quedan identificados como no evaluables cuando falta el
   contexto necesario.

5. **Las anomalías no confirman una avería.**  
   No se proporcionaron límites del fabricante, inspecciones ni resultados de
   mantenimiento. La acción recomendada es contrastar primero el período del
   7 al 13 de junio, junto con los casos aislados del 10 y 20 de mayo y 23 de junio,
   con bitácoras operativas, carga, intervenciones y condición del sensor.
"""
        )
        st.warning(
            "Conclusión operativa: priorizar la revisión del episodio de junio y "
            "mantener los registros marcados como candidatos de investigación, no "
            "como fallas confirmadas."
        )

    with time_tab:
        st.subheader("Vibración a lo largo del tiempo")
        time_data = filtered.dropna(subset=["fecha_hora", "vibracion_rms_mm_s"])
        time_figure = px.line(
            time_data,
            x="fecha_hora",
            y="vibracion_rms_mm_s",
            color="equipo_id",
            markers=True,
            labels={
                "fecha_hora": "Fecha y hora (zona no informada)",
                "vibracion_rms_mm_s": "Vibración (mm/s RMS)",
                "equipo_id": "Equipo",
            },
        )
        add_anomaly_trace(time_figure, filtered_anomalies, x="fecha_hora")
        time_figure.update_layout(legend_title_text="Serie")
        st.plotly_chart(time_figure, width="stretch")
        st.caption(
            "Las cruces rojas destacan registros inusuales para su contexto de RPM."
        )

    with relation_tab:
        st.subheader("Relación entre RPM y vibración")
        scatter_data = filtered.dropna(subset=["rpm", "vibracion_rms_mm_s"])
        scatter_figure = px.scatter(
            scatter_data,
            x="rpm",
            y="vibracion_rms_mm_s",
            color="equipo_id",
            hover_data={"source_row": True, "temperatura_c": ":.1f"},
            labels={
                "rpm": "Velocidad de operación (RPM)",
                "vibracion_rms_mm_s": "Vibración (mm/s RMS)",
                "equipo_id": "Equipo",
                "source_row": "Línea CSV",
                "temperatura_c": "Temperatura (°C)",
            },
        )
        add_anomaly_trace(scatter_figure, filtered_anomalies, x="rpm")
        scatter_figure.update_layout(legend_title_text="Serie")
        st.plotly_chart(scatter_figure, width="stretch")
        st.caption(
            "La vibración normalmente aumenta con las RPM; por eso la detección "
            "compara registros dentro de grupos de velocidad semejante."
        )

    with anomalies_tab:
        st.subheader("Registros para investigar")
        if filtered_anomalies.empty:
            st.info("No hay anomalías dentro de los filtros seleccionados.")
        else:
            displayed = filtered_anomalies[
                [
                    "source_row",
                    "fecha_hora",
                    "equipo_id",
                    "rpm",
                    "vibracion_rms_mm_s",
                    "temperatura_c",
                    "rpm_band",
                    "anomaly_score",
                    "upper_threshold",
                    "reason",
                ]
            ].rename(
                columns={
                    "source_row": "Línea CSV",
                    "fecha_hora": "Fecha y hora",
                    "equipo_id": "Equipo",
                    "rpm": "RPM",
                    "vibracion_rms_mm_s": "Vibración (mm/s RMS)",
                    "temperatura_c": "Temperatura (°C)",
                    "rpm_band": "Grupo RPM",
                    "anomaly_score": "Puntaje",
                    "upper_threshold": "Umbral superior",
                    "reason": "Motivo",
                }
            )
            st.dataframe(displayed, width="stretch", hide_index=True)
            st.download_button(
                "Descargar anomalías filtradas (CSV)",
                data=filtered_anomalies.to_csv(index=False).encode("utf-8-sig"),
                file_name="anomalias_filtradas.csv",
                mime="text/csv",
            )
        if not filtered_unevaluated.empty:
            st.warning(
                f"{len(filtered_unevaluated)} registro(s) no pudieron evaluarse por "
                "falta de RPM o vibración."
            )

    with method_tab:
        st.subheader("Cómo se identifican las anomalías")
        st.markdown(
            """
Los registros se dividen en ocho grupos con RPM semejantes. Dentro de cada grupo,
la vibración se compara con la mediana y la desviación absoluta mediana (MAD).
Se marca un registro cuando su distancia contextual absoluta supera 3,5 escalas
robustas.

Este umbral es una regla estadística exploratoria, no un límite de seguridad del
fabricante. Una marca indica que el registro merece revisión; no confirma una falla.
"""
        )
        st.dataframe(
            anomaly_result.band_baselines,
            width="stretch",
            hide_index=True,
        )


if __name__ == "__main__":
    main()

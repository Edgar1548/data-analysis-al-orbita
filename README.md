# Análisis de datos de un equipo industrial

[Aplicación publicada en Cloud Run](https://analysis-al-orbita-955223699476.us-central1.run.app) | [Repositorio público](https://github.com/Edgar1548/data-analysis-al-orbita)

Aplicación pequeña y explicable en Python para auditar mediciones operativas, resumir su comportamiento, identificar vibraciones inusuales para RPM semejantes y presentar los resultados mediante archivos, gráficas estáticas y una interfaz interactiva opcional.

El archivo fuente es `MBC_Prueba.csv`. La aplicación nunca lo sobrescribe.

## Requisitos

- Python 3. Personalmente use Python 3.14.2.
- Dependencias declaradas en `requirements.txt`: Pandas, NumPy, Matplotlib, Plotly y Streamlit.

## Instalación

Windows CMD:

```cmd
py -m venv .venv
.venv\Scripts\activate.bat
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -c "import pandas, numpy, matplotlib, plotly, streamlit; print('Dependencias correctas')"
```

Linux:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -c "import pandas, numpy, matplotlib, plotly, streamlit; print('Dependencias correctas')"
```

## Ejecutar el análisis completo

Desde la raíz del proyecto:

```console
python -m src.main MBC_Prueba.csv --output outputs
```

El comando genera:

```text
outputs/
├── quality_report.json
├── descriptive_statistics.csv
├── correlations.csv
├── rpm_group_summary.csv
├── weekly_summary.csv
├── time_trends.csv
├── anomalies.csv
├── anomaly_band_baselines.csv
├── anomaly_unevaluated_records.csv
├── vibration_over_time_RED-001.png
└── rpm_vs_vibration_RED-001.png
```

Los archivos generados están excluidos de Git porque pueden reproducirse a partir del CSV y del código fuente.

## Ejecutar la interfaz interactiva

```console
streamlit run app.py
```

Streamlit mostrará una dirección local, normalmente `http://localhost:8501`.

La interfaz permite:

- Filtrar por equipo y rango de fechas.
- Consultar estadísticas descriptivas y el reporte de calidad.
- Explorar la vibración temporal y su relación con las RPM.
- Ver las anomalías mediante marcadores interactivos y una tabla explicativa.
- Descargar las anomalías correspondientes a la selección visible.
- Consultar las líneas base utilizadas por el método.

Los filtros solo cambian la presentación. La clasificación se calcula sobre el conjunto completo para evitar que una anomalía cambie simplemente al seleccionar un período más corto.

## Ejecutar con Docker

Construir la imagen:

```console
docker build -t analisis-industrial .
```

Ejecutar el contenedor localmente:

```console
docker run --rm -p 8080:8080 -e PORT=8080 analisis-industrial
```

La aplicación estará disponible en `http://localhost:8080`. El contenedor escucha la variable `PORT` utilizada por Cloud Run y ejecuta el proceso con un usuario sin privilegios.

## Ejecutar las pruebas

```console
python -m unittest discover -s tests -v
```

Las pruebas cubren columnas obligatorias; valores faltantes, inválidos y no finitos; duplicados exactos y claves fecha/equipo repetidas; orden cronológico; estadísticas; anomalías y casos límite; creación de gráficas y filtrado inclusivo en la interfaz.

## Calidad y limpieza de datos

El CSV contiene 240 registros del equipo `RED-001`, desde el 1 de mayo hasta el 29 de junio de 2026, con mediciones cada seis horas.

Se encontraron cinco mediciones faltantes:

- RPM: líneas 53 y 121 del CSV.
- Vibración: líneas 44, 107 y 201 del CSV.

No se encontraron duplicados exactos, claves fecha/equipo repetidas, fechas inválidas, mediciones no numéricas con contenido, RPM negativas, vibraciones negativas ni temperaturas físicamente imposibles.

Las decisiones de limpieza son intencionalmente limitadas:

- Se conservan los 240 registros.
- Cada registro recibe `source_row`, su línea original en el CSV.
- Los valores faltantes permanecen faltantes; no se convierten en cero ni se interpolan.
- Los valores con un tipo inválido se convertirían en faltantes y quedarían registrados.
- Los registros se ordenan por fecha; una fecha inválida quedaría al final.
- Se permite RPM igual a cero porque el equipo podría estar detenido.
- El CSV original no se modifica.

## Resultados descriptivos

| Medición | Cantidad válida | Promedio | Mínimo | Máximo | Desviación estándar muestral |
|---|---:|---:|---:|---:|---:|
| RPM | 238 | 850.269 | 385 | 1,382 | 324.753 |
| Vibración (mm/s RMS) | 237 | 2.481 | 1.447 | 4.674 | 0.638 |
| Temperatura (°C) | 240 | 54.306 | 44.3 | 65.9 | 4.699 |

Los valores faltantes se omiten únicamente del cálculo que los necesita. Un registro incompleto no se elimina de todos los demás análisis.

RPM y vibración presentan correlación de Pearson de 0.759 y correlación de Spearman de 0.811, calculadas con 235 pares completos. Temperatura y vibración presentan correlaciones de 0.691 y 0.753 respectivamente, con 237 pares completos. Estas relaciones son asociaciones estadísticas; no demuestran causalidad.

El promedio y la mediana de vibración aumentan entre los grupos de RPM. Por ello, un único umbral global ignoraría la velocidad operativa y podría clasificar incorrectamente un comportamiento esperado a RPM altas.

La semana que comienza el 5 de junio tiene una vibración promedio de 3.055 mm/s RMS con aproximadamente 800 RPM en promedio. Es un período inusual que merece investigación, pero los datos no establecen una causa mecánica.

## Conclusiones principales

1. **Las RPM son necesarias para interpretar la vibración.** La asociación positiva y el aumento progresivo de la vibración entre grupos de velocidad muestran que una lectura alta puede ser normal cuando el equipo opera a RPM altas. Un único umbral global ignoraría este contexto.

2. **El principal comportamiento inusual aparece entre el 7 y el 13 de junio.** En este período se concentran 18 de las 21 anomalías identificadas. La concentración temporal justifica revisar qué condición operativa cambió durante esos días.

3. **También existen tres casos aislados que requieren revisión:** 10 de mayo, 20 de mayo y 23 de junio. El registro del 20 de mayo está apenas por encima del criterio estadístico y es sensible a la línea base seleccionada.

4. **Temperatura y vibración presentan una asociación positiva, pero no puede afirmarse causalidad.** Faltan variables como carga, modo operativo, intervenciones y condición del sensor.

5. **Las anomalías no confirman una falla mecánica.** No se proporcionaron límites del fabricante, diagnósticos ni resultados de mantenimiento. Los registros marcados deben considerarse candidatos de investigación.

La acción recomendada es revisar primero las bitácoras operativas y de mantenimiento correspondientes al período del 7 al 13 de junio. Después deben analizarse los tres casos aislados y confirmarse la condición del sensor.

## Método de detección de anomalías

Los registros con RPM y vibración completas se dividen en ocho grupos con cantidades semejantes y RPM comparables. Dentro de cada grupo:

```text
escala robusta = MAD / 0.67448975
puntaje contextual = (vibración - mediana del grupo) / escala robusta
marcar cuando el valor absoluto del puntaje sea mayor que 3.5
```

MAD significa desviación absoluta mediana. La mediana y MAD son menos sensibles a unas pocas mediciones extremas que el promedio y la desviación estándar.

Cada grupo necesita por lo menos 15 registros. Si MAD es cero, se utiliza la desviación estándar muestral y se documenta el cambio. Si tampoco existe dispersión medible, el grupo queda sin evaluar.

El método marca 21 de los 235 registros con RPM y vibración completas. Dieciocho aparecen entre el 7 y el 13 de junio. Cinco registros incompletos quedan explícitamente identificados como no evaluados.

Cada anomalía conserva la línea original, fecha, equipo, mediciones, grupo de RPM, puntaje, umbrales, regla y explicación en `outputs/anomalies.csv`.

El valor 3.5 es un criterio estadístico exploratorio, no un límite de seguridad. Una marca significa “investigar esta medición”, no “falla mecánica confirmada”. La tabla completa se genera en `outputs/anomalies.csv`.

## Visualizaciones

La ejecución principal crea dos gráficas estáticas por equipo:

- Vibración a lo largo del tiempo, para mostrar cuándo ocurre el comportamiento inusual.
- RPM frente a vibración, para mostrar si una medición es inusual para su velocidad operativa.

Las anomalías aparecen como cruces rojas. Los registros sin el valor requerido por un eje se omiten en vez de representarse como cero. Streamlit presenta versiones interactivas de estas vistas y conserva la misma tabla de anomalías.

## Estructura del proyecto

```text
app.py                         # Interfaz interactiva Streamlit

src/
├── data_quality.py            # Carga, tipos, auditoría y ordenamiento
├── analysis.py                # Estadísticas y exploración
├── anomaly_detection.py       # Detección contextual de vibración
├── visualization.py           # Gráficas estáticas
└── main.py                    # Ejecución completa por consola

tests/
├── test_data_quality.py
├── test_analysis.py
├── test_anomaly_detection.py
├── test_visualization.py
└── test_dashboard.py
```

## Limitaciones

- Solo se dispone de un equipo y aproximadamente dos meses de información.
- No existen resultados de mantenimiento, etiquetas de fallas, carga ni modo operativo.
- No se proporcionaron límites del fabricante ni límites de ingeniería.
- Los grupos de RPM provienen de los datos y no son rangos operativos aprobados.
- Las correlaciones y tendencias temporales no prueban causalidad.
- Varias anomalías consecutivas podrían representar un solo episodio sostenido.
- Los resultados pueden cambiar al incorporar un historial mucho mayor.

## Mejoras posibles

- Contrastar los períodos señalados con registros de operación y mantenimiento.
- Incorporar carga o modo operativo si esos datos están disponibles.
- Sustituir los grupos calculados por rangos de ingeniería aprobados.
- Reevaluar el umbral con un historial mayor y registrar falsos positivos.

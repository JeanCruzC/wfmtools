# Calculadora WFM - Examen Planeamiento

Aplicación web lista para GitHub + Coolify que convierte el archivo **Examen Planeamiento** en una calculadora WFM editable.

La app carga por defecto todos los valores de la evaluación y recalcula automáticamente los mismos bloques del Excel:

- **Ejercicio 1:** AHT inbound.
- **Ejercicio 2:** horas presentes y horas programadas requeridas.
- **Ejercicio 3:** AHT por turno y AHT global.
- **Dimensionado:** agentes requeridos por día, HC + shrinkage, FTE, mix FT/PT y referencia Erlang C.
- **Caso de estudio:** KPIs globales y análisis por mes, semana, día y hora usando los registros del examen.
- **Carga de datos:** importación de CSV/XLSX con la misma estructura de la hoja `3. Caso de Estudio`.

## Valores default incluidos

La aplicación viene precargada con los datos originales del examen:

- Ejercicio 1: scheduled hours, ausentismo, auxiliares, availtime, NDA, NDS y llamadas.
- Ejercicio 2: AHT, llamadas, NDA, ocupación, horas Back Office, horas Email, vacaciones y auxiliares.
- Ejercicio 3: los 5 turnos con llamadas atendidas, conversación, ACW, agentes y horas logadas.
- Dimensionado: 99,687 llamadas semanales, AHT 389, shrinkage, ocupación, SLA 80/20, horas FT/PT, distribución diaria y 30% PT.
- Caso de estudio: registros históricos de llamadas del Excel.

## Resultados esperados con el default del examen

Al abrir la calculadora sin cambiar nada, debe mostrar aproximadamente:

- AHT inbound: **358.500 seg**.
- Horas presentes: **3,622.778**.
- Horas programadas: **3,734.822**.
- AHT global turnos: **301.158 seg**.
- Dimensionado HC + shrinkage por día: Lunes 263, Martes 251, Miércoles 227, Jueves 214, Viernes 164, Sábado 184.

## Stack técnico

- Backend: **FastAPI**.
- Base de datos: **SQLite** persistente.
- Frontend: **React + Vite**.
- Contenedor: **Docker**.

## Ejecutar localmente con Docker

```bash
docker compose up --build
```

Luego abre:

```text
http://localhost:8080
```

## Desplegar en Coolify

1. Sube esta carpeta a un repositorio de GitHub.
2. En Coolify crea una nueva aplicación desde ese repositorio.
3. Tipo de build: **Dockerfile**.
4. Puerto expuesto: **8080**.
5. Agrega un volumen persistente:

```text
/data
```

6. Variables recomendadas:

```text
DATABASE_PATH=/data/app.db
CORS_ORIGINS=*
```

La app usa `/data/app.db` para guardar escenarios modificados y registros cargados.

## Version alternativa en Streamlit

Si quieres montar una version rapida en Streamlit (sin frontend React), usa:

```bash
pip install -r requirements-streamlit.txt -r backend/requirements.txt
streamlit run streamlit_app.py --server.port 8501
```

La app reutiliza los mismos calculos de:

- `backend/app/calculations.py`

Para desplegar en Streamlit Cloud:

1. Repo: este mismo.
2. Main file path: `streamlit_app.py`.
3. Python version: 3.12 (recomendado).
4. Dependencias: `requirements-streamlit.txt` y `backend/requirements.txt` (puedes unificarlas en un solo `requirements.txt` si prefieres).

## Estructura esperada para importar registros

Acepta CSV o XLSX con encabezados equivalentes a:

```text
mes, fecha, semana, hora, Recibidas, Atendidas, abandonada, Atendidas dentro de SLA, AHT_Seg, TME_Seg
```

Notas:

- `fecha` debe estar como `YYYYMMDD` o fecha reconocible.
- `hora` debe estar entre 0 y 23.
- Si `abandonada` no viene, se calcula como `recibidas - atendidas`.
- Puedes reemplazar los datos del ejemplo o agregarlos.

## Endpoints principales

- `GET /api/scenarios/exercises`: valores editables de ejercicios.
- `GET /api/scenarios/dimensioning`: valores editables del dimensionado.
- `POST /api/calculators/exercises`: recalcula ejercicios.
- `POST /api/calculators/dimensioning`: recalcula dimensionado.
- `GET /api/analytics`: KPIs del caso de estudio.
- `POST /api/records/upload`: carga CSV/XLSX.
- `POST /api/reset-demo`: restaura todo el examen default.

## Notas de cálculo

El dimensionado principal replica la lógica del Excel:

```text
Shrinkage = 1 / ((1 - Ausentismo) × (1 - Auxiliares))
Llamadas día = Llamadas semana × % tráfico
Calls por hora = Llamadas día / horas operativas
Tráfico Erlang = Calls por hora × AHT / 3600
Agentes posición = ROUNDUP(Tráfico Erlang / Ocupación objetivo)
HC + shrinkage = ROUNDUP(Agentes posición × Shrinkage)
```

Adicionalmente se calcula una referencia Erlang C por día para comparar contra SLA objetivo.

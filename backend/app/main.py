from __future__ import annotations

import csv
import datetime as dt
import io
import json
import os
import re
import unicodedata
from pathlib import Path
from typing import Any, Literal

from fastapi import Body, FastAPI, File, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .calculations import calculate_dimensioning, calculate_exercises, safe_div
from .database import get_conn, get_scenario, init_db, load_json_file, upsert_scenario

APP_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = APP_DIR / "data"
STATIC_DIR = APP_DIR / "static"

DAY_LABELS = {
    1: "Lunes",
    2: "Martes",
    3: "Miércoles",
    4: "Jueves",
    5: "Viernes",
    6: "Sábado",
    7: "Domingo",
}
MONTH_LABELS = {
    1: "Ene",
    2: "Feb",
    3: "Mar",
    4: "Abr",
    5: "May",
    6: "Jun",
    7: "Jul",
    8: "Ago",
    9: "Sep",
    10: "Oct",
    11: "Nov",
    12: "Dic",
}

app = FastAPI(
    title="Planeamiento WFM",
    description="App para replicar y extender los cálculos del examen de planeamiento.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ORIGINS", "*").split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)


class RecordIn(BaseModel):
    mes: int | None = None
    fecha: int
    semana: str
    hora: int = Field(ge=0, le=23)
    recibidas: int = Field(ge=0)
    atendidas: int = Field(ge=0)
    abandonada: int | None = Field(default=None, ge=0)
    atendidas_sla: int = Field(ge=0)
    aht_seg: float = Field(ge=0)
    tme_seg: float = Field(ge=0)


class ScenarioIn(BaseModel):
    name: str
    payload: dict[str, Any]


def normalize_key(value: Any) -> str:
    text = "" if value is None else str(value)
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    text = text.strip().lower()
    text = re.sub(r"[\s_\-\.]+", " ", text)
    return text


HEADER_ALIASES = {
    "mes": "mes",
    "fecha": "fecha",
    "semana": "semana",
    "hora": "hora",
    "recibidas": "recibidas",
    "llamadas recibidas": "recibidas",
    "atendidas": "atendidas",
    "llamadas atendidas": "atendidas",
    "abandonada": "abandonada",
    "abandonadas": "abandonada",
    "llamadas abandonadas": "abandonada",
    "atendidas dentro de sla": "atendidas_sla",
    "atendidas sla": "atendidas_sla",
    "dentro de sla": "atendidas_sla",
    "answered within sla": "atendidas_sla",
    "aht seg": "aht_seg",
    "aht_seg": "aht_seg",
    "aht": "aht_seg",
    "tme seg": "tme_seg",
    "tme_seg": "tme_seg",
    "asa": "tme_seg",
    "diasem": "dia_sem",
    "dia sem": "dia_sem",
    "dia semana": "dia_sem",
}


def parse_date_int(value: Any) -> int:
    if isinstance(value, dt.datetime | dt.date):
        return int(value.strftime("%Y%m%d"))
    if isinstance(value, float) and value.is_integer():
        return int(value)
    if isinstance(value, int):
        return value
    text = str(value).strip()
    if re.fullmatch(r"\d{8}", text):
        return int(text)
    match = re.search(r"(\d{4})[-/](\d{1,2})[-/](\d{1,2})", text)
    if match:
        y, m, d = [int(x) for x in match.groups()]
        return y * 10000 + m * 100 + d
    raise ValueError(f"Fecha inválida: {value!r}")


def day_of_week(fecha: int) -> int:
    text = str(int(fecha))
    return dt.date(int(text[:4]), int(text[4:6]), int(text[6:8])).isoweekday()


def month_from_date(fecha: int) -> int:
    return int(str(int(fecha))[:6])


def as_int(value: Any, default: int = 0) -> int:
    if value is None or value == "":
        return default
    return int(float(value))


def as_float(value: Any, default: float = 0) -> float:
    if value is None or value == "":
        return default
    return float(value)


def normalize_record(raw: dict[str, Any], source: str) -> tuple:
    fecha = parse_date_int(raw.get("fecha"))
    mes = as_int(raw.get("mes"), month_from_date(fecha))
    semana = str(raw.get("semana", "")).strip()
    if not semana:
        raise ValueError("La columna semana es requerida.")
    hora = as_int(raw.get("hora"))
    recibidas = as_int(raw.get("recibidas"))
    atendidas = as_int(raw.get("atendidas"))
    abandonada = raw.get("abandonada")
    abandonada = as_int(abandonada, max(recibidas - atendidas, 0))
    atendidas_sla = as_int(raw.get("atendidas_sla"))
    aht_seg = as_float(raw.get("aht_seg"))
    tme_seg = as_float(raw.get("tme_seg"))
    dia_sem = day_of_week(fecha)

    return (
        mes,
        fecha,
        semana,
        hora,
        recibidas,
        atendidas,
        abandonada,
        atendidas_sla,
        aht_seg,
        tme_seg,
        dia_sem,
        source,
    )


def insert_records(records: list[tuple]) -> int:
    if not records:
        return 0
    with get_conn() as conn:
        conn.executemany(
            """
            INSERT INTO call_records (
                mes, fecha, semana, hora, recibidas, atendidas, abandonada,
                atendidas_sla, aht_seg, tme_seg, dia_sem, source
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            records,
        )
    return len(records)


def clear_records() -> None:
    with get_conn() as conn:
        conn.execute("DELETE FROM call_records")
        conn.execute("DELETE FROM sqlite_sequence WHERE name = 'call_records'")


def parse_csv_bytes(content: bytes, source: str) -> list[tuple]:
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = content.decode("latin-1")
    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        raise ValueError("El archivo CSV no tiene encabezados.")

    mapping = {}
    for header in reader.fieldnames:
        canonical = HEADER_ALIASES.get(normalize_key(header))
        if canonical:
            mapping[header] = canonical

    required = {"fecha", "semana", "hora", "recibidas", "atendidas", "atendidas_sla", "aht_seg", "tme_seg"}
    if not required.issubset(set(mapping.values())):
        missing = sorted(required - set(mapping.values()))
        raise ValueError(f"Faltan columnas requeridas: {', '.join(missing)}")

    records = []
    for row in reader:
        raw = {mapping[key]: value for key, value in row.items() if key in mapping}
        if not any(raw.values()):
            continue
        records.append(normalize_record(raw, source))
    return records


def parse_xlsx_bytes(content: bytes, source: str) -> list[tuple]:
    try:
        import openpyxl
    except ImportError as exc:
        raise ValueError("Para importar XLSX instala openpyxl en el backend.") from exc

    workbook = openpyxl.load_workbook(io.BytesIO(content), data_only=True, read_only=True)
    best_rows: list[tuple] = []
    best_count = 0

    for sheet in workbook.worksheets:
        rows_iter = sheet.iter_rows(values_only=True)
        for header_row in rows_iter:
            normalized_headers = [HEADER_ALIASES.get(normalize_key(cell)) for cell in header_row]
            if "fecha" not in normalized_headers or "recibidas" not in normalized_headers:
                continue

            records: list[tuple] = []
            for values in rows_iter:
                raw = {}
                for index, canonical in enumerate(normalized_headers):
                    if canonical and index < len(values):
                        raw[canonical] = values[index]
                if not raw or raw.get("fecha") in (None, ""):
                    continue
                try:
                    records.append(normalize_record(raw, source))
                except Exception:
                    # Saltamos filas de resumen o fórmulas fuera de la tabla.
                    continue

            if len(records) > best_count:
                best_rows = records
                best_count = len(records)
            break

    if not best_rows:
        raise ValueError("No encontré una hoja con encabezados compatibles.")
    return best_rows


def seed_scenarios_if_empty() -> None:
    example = load_json_file(DATA_DIR / "example_inputs.json")
    if get_scenario("exercises") is None:
        upsert_scenario("exercises", "Ejercicios del examen", example["exercises"])
    if get_scenario("dimensioning") is None:
        upsert_scenario("dimensioning", "Dimensionado base", example["dimensioning"])


def seed_records_if_empty() -> None:
    with get_conn() as conn:
        count = conn.execute("SELECT COUNT(*) AS total FROM call_records").fetchone()["total"]
    if count:
        return
    content = (DATA_DIR / "sample_records.csv").read_bytes()
    records = parse_csv_bytes(content, "ejemplo-examen")
    insert_records(records)


@app.on_event("startup")
def startup() -> None:
    init_db()
    seed_scenarios_if_empty()
    seed_records_if_empty()


@app.get("/api/health")
def health() -> dict[str, Any]:
    with get_conn() as conn:
        records = conn.execute("SELECT COUNT(*) AS total FROM call_records").fetchone()["total"]
    return {"ok": True, "records": records}


@app.get("/api/scenarios/{kind}")
def read_scenario(kind: Literal["exercises", "dimensioning"]) -> dict[str, Any]:
    scenario = get_scenario(kind)
    if not scenario:
        raise HTTPException(status_code=404, detail="Escenario no encontrado.")
    return scenario


@app.put("/api/scenarios/{kind}")
def save_scenario(kind: Literal["exercises", "dimensioning"], payload: ScenarioIn) -> dict[str, Any]:
    upsert_scenario(kind, payload.name, payload.payload)
    return read_scenario(kind)


@app.get("/api/records")
def list_records(limit: int = Query(100, ge=1, le=1000), offset: int = Query(0, ge=0)) -> dict[str, Any]:
    with get_conn() as conn:
        total = conn.execute("SELECT COUNT(*) AS total FROM call_records").fetchone()["total"]
        rows = conn.execute(
            """
            SELECT id, mes, fecha, semana, hora, recibidas, atendidas, abandonada,
                   atendidas_sla, aht_seg, tme_seg, dia_sem, source, created_at
            FROM call_records
            ORDER BY fecha, hora
            LIMIT ? OFFSET ?
            """,
            (limit, offset),
        ).fetchall()
    return {"total": total, "items": [dict(row) for row in rows]}


@app.post("/api/records")
def create_record(record: RecordIn) -> dict[str, Any]:
    raw = record.model_dump()
    normalized = normalize_record(raw, "manual")
    insert_records([normalized])
    return {"inserted": 1}


@app.post("/api/records/upload")
async def upload_records(
    file: UploadFile = File(...),
    mode: Literal["append", "replace"] = Query("append"),
) -> dict[str, Any]:
    content = await file.read()
    filename = file.filename or "upload"
    suffix = Path(filename).suffix.lower()

    try:
        if suffix == ".csv":
            records = parse_csv_bytes(content, filename)
        elif suffix in {".xlsx", ".xlsm"}:
            records = parse_xlsx_bytes(content, filename)
        else:
            raise ValueError("Formato no soportado. Usa CSV o XLSX.")
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if mode == "replace":
        clear_records()
    inserted = insert_records(records)
    return {"inserted": inserted, "mode": mode, "filename": filename}


@app.post("/api/reset-demo")
def reset_demo() -> dict[str, Any]:
    clear_records()
    content = (DATA_DIR / "sample_records.csv").read_bytes()
    records = parse_csv_bytes(content, "ejemplo-examen")
    inserted = insert_records(records)

    example = load_json_file(DATA_DIR / "example_inputs.json")
    upsert_scenario("exercises", "Ejercicios del examen", example["exercises"])
    upsert_scenario("dimensioning", "Dimensionado base", example["dimensioning"])

    return {"inserted": inserted, "message": "Datos de ejemplo restaurados."}


def aggregate_row(row: Any, label: str | None = None) -> dict[str, Any]:
    recibidas = row["recibidas"] or 0
    atendidas = row["atendidas"] or 0
    abandonada = row["abandonada"] or 0
    atendidas_sla = row["atendidas_sla"] or 0
    weighted_aht = row["weighted_aht"] or 0
    weighted_tme = row["weighted_tme"] or 0
    payload = {
        "recibidas": recibidas,
        "atendidas": atendidas,
        "abandonadas": abandonada,
        "atendidas_sla": atendidas_sla,
        "answer_rate": safe_div(atendidas, recibidas),
        "abandon_rate": safe_div(abandonada, recibidas),
        "sla": safe_div(atendidas_sla, atendidas),
        "aht_pond": safe_div(weighted_aht, atendidas),
        "asa": safe_div(weighted_tme, atendidas),
    }
    if label is not None:
        payload["label"] = label
    return payload


def month_label(yyyymm: int) -> str:
    text = str(int(yyyymm))
    month = int(text[4:6])
    year = text[2:4]
    return f"{MONTH_LABELS.get(month, text[4:6])}-{year}"


def group_query(group_expr: str, order_expr: str) -> list[Any]:
    with get_conn() as conn:
        return conn.execute(
            f"""
            SELECT {group_expr} AS group_key,
                   SUM(recibidas) AS recibidas,
                   SUM(atendidas) AS atendidas,
                   SUM(abandonada) AS abandonada,
                   SUM(atendidas_sla) AS atendidas_sla,
                   SUM(aht_seg * atendidas) AS weighted_aht,
                   SUM(tme_seg * atendidas) AS weighted_tme
            FROM call_records
            GROUP BY {group_expr}
            ORDER BY {order_expr}
            """
        ).fetchall()


@app.get("/api/analytics")
def analytics() -> dict[str, Any]:
    with get_conn() as conn:
        total_rows = conn.execute("SELECT COUNT(*) AS total FROM call_records").fetchone()["total"]
        global_row = conn.execute(
            """
            SELECT SUM(recibidas) AS recibidas,
                   SUM(atendidas) AS atendidas,
                   SUM(abandonada) AS abandonada,
                   SUM(atendidas_sla) AS atendidas_sla,
                   SUM(aht_seg * atendidas) AS weighted_aht,
                   SUM(tme_seg * atendidas) AS weighted_tme
            FROM call_records
            """
        ).fetchone()

    global_kpis = aggregate_row(global_row)
    by_month = [aggregate_row(row, month_label(row["group_key"])) | {"mes": row["group_key"]} for row in group_query("mes", "mes")]
    by_week = [aggregate_row(row, row["group_key"]) for row in group_query("semana", "CAST(SUBSTR(semana, 4) AS INTEGER), semana")]
    by_day = [aggregate_row(row, DAY_LABELS.get(row["group_key"], str(row["group_key"]))) | {"dia_sem": row["group_key"]} for row in group_query("dia_sem", "dia_sem")]
    by_hour = [aggregate_row(row, f"{int(row['group_key']):02d}:00") | {"hora": row["group_key"]} for row in group_query("hora", "hora")]

    critical_month = min(by_month, key=lambda row: row["sla"], default=None)
    critical_day = min(by_day, key=lambda row: row["sla"], default=None)
    peak_hour = max(by_hour, key=lambda row: row["recibidas"], default=None)

    return {
        "total_rows": total_rows,
        "global": global_kpis,
        "by_month": by_month,
        "by_week": by_week,
        "by_day": by_day,
        "by_hour": by_hour,
        "insights": {
            "critical_month": critical_month,
            "critical_day": critical_day,
            "peak_hour": peak_hour,
        },
    }


@app.post("/api/calculators/exercises")
def run_exercises(payload: dict[str, Any] | None = Body(default=None)) -> dict[str, Any]:
    if payload is None:
        scenario = get_scenario("exercises")
        payload = scenario["payload"] if scenario else {}
    return calculate_exercises(payload)


@app.post("/api/calculators/dimensioning")
def run_dimensioning(payload: dict[str, Any] | None = Body(default=None)) -> dict[str, Any]:
    if payload is None:
        scenario = get_scenario("dimensioning")
        payload = scenario["payload"] if scenario else {}
    return calculate_dimensioning(payload)


if STATIC_DIR.exists():
    assets_dir = STATIC_DIR / "assets"
    if assets_dir.exists():
        app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")


@app.get("/{full_path:path}")
def serve_spa(full_path: str) -> FileResponse:
    index_path = STATIC_DIR / "index.html"
    requested = STATIC_DIR / full_path
    if full_path and requested.exists() and requested.is_file():
        return FileResponse(requested)
    if index_path.exists():
        return FileResponse(index_path)
    raise HTTPException(status_code=404, detail="Frontend no construido. Ejecuta npm run build o usa Docker.")

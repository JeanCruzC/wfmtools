from __future__ import annotations

import json
import re
import unicodedata
from copy import deepcopy
from pathlib import Path

import pandas as pd
import streamlit as st

from backend.app.calculations import calculate_dimensioning, calculate_exercises

DATA_FILE = Path(__file__).resolve().parent / "data" / "example_inputs.json"
RECORDS_FILE = Path(__file__).resolve().parent / "data" / "sample_records.csv"


def load_defaults() -> dict:
    return json.loads(DATA_FILE.read_text(encoding="utf-8"))


def p(value: float) -> str:
    return f"{value * 100:.2f}%"


def n(value: float) -> str:
    return f"{value:,.3f}"


def to_num(value: object, default: float = 0.0) -> float:
    if value is None:
        return default
    text = str(value).strip()
    if text == "" or text.lower() == "nan":
        return default
    text = text.replace(",", "")
    try:
        return float(text)
    except Exception:
        return default


def sanitize_shifts(rows: list[dict]) -> list[dict]:
    cleaned = []
    for idx, row in enumerate(rows):
        if not isinstance(row, dict):
            continue
        shift_name = str(row.get("shift", f"Turno {idx + 1}")).strip() or f"Turno {idx + 1}"
        cleaned.append(
            {
                "shift": shift_name,
                "answered_calls": to_num(row.get("answered_calls"), 0.0),
                "talk_minutes": to_num(row.get("talk_minutes"), 0.0),
                "acw_minutes": to_num(row.get("acw_minutes"), 0.0),
                "agents": to_num(row.get("agents"), 0.0),
                "logged_hours": to_num(row.get("logged_hours"), 0.0),
            }
        )
    return cleaned


def norm_col(name: object) -> str:
    text = "" if name is None else str(name)
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    text = text.strip().lower()
    text = re.sub(r"[\s_\-\.]+", "", text)
    return text


def editable_sheet(title: str, rows: list[dict], key: str) -> pd.DataFrame:
    st.markdown(f"#### {title}")
    df = pd.DataFrame(rows)
    return st.data_editor(df, use_container_width=True, hide_index=True, key=key)


def style_deviation_table(df: pd.DataFrame, sla_col: str = "SLA", abandon_col: str = "Abandono"):
    def color_sla(v):
        try:
            val = float(v)
        except Exception:
            return ""
        if val < 0.7:
            return "background-color:#7f1d1d;color:#fee2e2;font-weight:700;"
        if val < 0.8:
            return "background-color:#78350f;color:#fef3c7;font-weight:700;"
        return "background-color:#14532d;color:#dcfce7;font-weight:700;"

    def color_ab(v):
        try:
            val = float(v)
        except Exception:
            return ""
        if val > 0.12:
            return "background-color:#7f1d1d;color:#fee2e2;font-weight:700;"
        if val > 0.08:
            return "background-color:#78350f;color:#fef3c7;font-weight:700;"
        return "background-color:#14532d;color:#dcfce7;font-weight:700;"

    styler = df.style
    if sla_col in df.columns:
        styler = styler.map(color_sla, subset=[sla_col])
    if abandon_col in df.columns:
        styler = styler.map(color_ab, subset=[abandon_col])
    return styler


def case_study_kpis() -> dict:
    df = pd.read_csv(RECORDS_FILE)
    col_map = {norm_col(c): c for c in df.columns}

    def col(*aliases: str) -> str:
        for a in aliases:
            key = norm_col(a)
            if key in col_map:
                return col_map[key]
        raise KeyError(f"No se encontro ninguna columna para aliases={aliases}")

    c_received = col("Recibidas")
    c_answered = col("Atendidas")
    c_abandoned = col("abandonada", "abandonadas")
    c_sla = col("Atendidas dentro de SLA", "atendidas_sla")
    c_aht = col("AHT_Seg", "aht")
    c_tme = col("TME_Seg", "asa")
    c_day = col("DiaSem", "dia_sem")
    c_hour = col("hora")

    received = float(df[c_received].sum())
    answered = float(df[c_answered].sum())
    abandoned = float(df[c_abandoned].sum())
    sla_ans = float(df[c_sla].sum())
    weighted_aht = float((df[c_aht] * df[c_answered]).sum())
    weighted_tme = float((df[c_tme] * df[c_answered]).sum())

    global_kpi = {
        "recibidas": received,
        "atendidas": answered,
        "abandonadas": abandoned,
        "sla": (sla_ans / answered) if answered else 0.0,
        "abandono": (abandoned / received) if received else 0.0,
        "aht": (weighted_aht / answered) if answered else 0.0,
        "asa": (weighted_tme / answered) if answered else 0.0,
    }

    by_day = (
        df.groupby(c_day, as_index=False)
        .agg({c_received: "sum", c_answered: "sum", c_abandoned: "sum", c_sla: "sum"})
        .rename(columns={c_sla: "sla_ans", c_received: "recibidas", c_answered: "atendidas", c_abandoned: "abandonada", c_day: "DiaSem"})
    )
    by_day["sla"] = by_day["sla_ans"] / by_day["atendidas"].replace(0, 1)
    critical_day = by_day.sort_values("sla").iloc[0].to_dict()

    by_hour = df.groupby(c_hour, as_index=False).agg({c_received: "sum"}).rename(columns={c_hour: "hora", c_received: "Recibidas"}).sort_values("Recibidas", ascending=False)
    peak_hour = by_hour.iloc[0].to_dict()

    month_map = {1: "Ene", 2: "Feb", 3: "Mar", 4: "Abr", 5: "May", 6: "Jun", 7: "Jul", 8: "Ago", 9: "Sep", 10: "Oct", 11: "Nov", 12: "Dic"}
    day_map = {1: "Lunes", 2: "Martes", 3: "Miercoles", 4: "Jueves", 5: "Viernes", 6: "Sabado", 7: "Domingo"}

    by_month = (
        df.groupby(col("mes"), as_index=False)
        .agg({c_received: "sum", c_answered: "sum", c_abandoned: "sum", c_sla: "sum"})
        .rename(columns={c_received: "recibidas", c_answered: "atendidas", c_abandoned: "abandonadas", c_sla: "atendidas_sla"})
    )
    by_month["answer_rate"] = by_month["atendidas"] / by_month["recibidas"].replace(0, 1)
    by_month["abandon_rate"] = by_month["abandonadas"] / by_month["recibidas"].replace(0, 1)
    by_month["sla"] = by_month["atendidas_sla"] / by_month["atendidas"].replace(0, 1)
    by_month["label"] = by_month[col("mes")].astype(str).apply(lambda x: f"{month_map.get(int(x[4:6]), x[4:6])}-{x[2:4]}")

    by_week = (
        df.groupby(col("semana"), as_index=False)
        .agg({c_received: "sum", c_answered: "sum", c_abandoned: "sum", c_sla: "sum"})
        .rename(columns={col("semana"): "semana", c_received: "recibidas", c_answered: "atendidas", c_abandoned: "abandonadas", c_sla: "atendidas_sla"})
    )
    by_week["sem_num"] = by_week["semana"].astype(str).str.extract(r"(\d+)").astype(float).fillna(0)
    by_week = by_week.sort_values("sem_num")
    by_week["answer_rate"] = by_week["atendidas"] / by_week["recibidas"].replace(0, 1)
    by_week["abandon_rate"] = by_week["abandonadas"] / by_week["recibidas"].replace(0, 1)
    by_week["sla"] = by_week["atendidas_sla"] / by_week["atendidas"].replace(0, 1)
    by_week["forecast_prev"] = by_week["recibidas"].shift(1)
    mape_df = by_week.dropna(subset=["forecast_prev"]).copy()
    mape = float(((mape_df["recibidas"] - mape_df["forecast_prev"]).abs() / mape_df["recibidas"].replace(0, 1)).mean()) if not mape_df.empty else 0.0

    by_day_named = by_day.copy()
    by_day_named["dia"] = by_day_named["DiaSem"].map(day_map).fillna(by_day_named["DiaSem"].astype(str))
    by_day_named["answer_rate"] = by_day_named["atendidas"] / by_day_named["recibidas"].replace(0, 1)
    by_day_named["abandon_rate"] = by_day_named["abandonada"] / by_day_named["recibidas"].replace(0, 1)

    hour_kpi = (
        df.groupby(c_hour, as_index=False)
        .agg({c_received: "sum", c_answered: "sum", c_abandoned: "sum", c_sla: "sum"})
        .rename(columns={c_hour: "hora", c_received: "recibidas", c_answered: "atendidas", c_abandoned: "abandonadas", c_sla: "atendidas_sla"})
        .sort_values("hora")
    )
    hour_kpi["answer_rate"] = hour_kpi["atendidas"] / hour_kpi["recibidas"].replace(0, 1)
    hour_kpi["abandon_rate"] = hour_kpi["abandonadas"] / hour_kpi["recibidas"].replace(0, 1)
    hour_kpi["sla"] = hour_kpi["atendidas_sla"] / hour_kpi["atendidas"].replace(0, 1)
    hour_kpi["franja"] = hour_kpi["hora"].astype(int).astype(str).str.zfill(2) + ":00"

    alerts = []
    if global_kpi["sla"] < 0.8:
        alerts.append("SLA global por debajo del objetivo 80/20.")
    if global_kpi["abandono"] > 0.08:
        alerts.append("Tasa de abandono alta a nivel global (>8%).")
    if mape > 0.2:
        alerts.append("Alta variabilidad semanal de demanda (MAPE > 20%).")
    if not alerts:
        alerts.append("Indicadores globales en rango esperado.")

    # Desviaciones clave para priorizacion visual
    by_week_dev = by_week.copy()
    by_week_dev["sla_gap"] = 0.8 - by_week_dev["sla"]
    by_week_dev["aband_gap"] = by_week_dev["abandon_rate"] - 0.08
    by_week_dev["risk_score"] = by_week_dev["sla_gap"].clip(lower=0) * 100 + by_week_dev["aband_gap"].clip(lower=0) * 100
    worst_week = by_week_dev.sort_values("risk_score", ascending=False).iloc[0].to_dict() if not by_week_dev.empty else {}

    by_hour_dev = hour_kpi.copy()
    by_hour_dev["sla_gap"] = 0.8 - by_hour_dev["sla"]
    by_hour_dev["aband_gap"] = by_hour_dev["abandon_rate"] - 0.08
    by_hour_dev["risk_score"] = by_hour_dev["sla_gap"].clip(lower=0) * 100 + by_hour_dev["aband_gap"].clip(lower=0) * 100
    worst_hour = by_hour_dev.sort_values("risk_score", ascending=False).iloc[0].to_dict() if not by_hour_dev.empty else {}

    by_day_dev = by_day_named.copy()
    by_day_dev["sla_gap"] = 0.8 - by_day_dev["sla"]
    by_day_dev["aband_gap"] = by_day_dev["abandon_rate"] - 0.08
    by_day_dev["risk_score"] = by_day_dev["sla_gap"].clip(lower=0) * 100 + by_day_dev["aband_gap"].clip(lower=0) * 100
    worst_day = by_day_dev.sort_values("risk_score", ascending=False).iloc[0].to_dict() if not by_day_dev.empty else {}

    dynamic_recs = []
    if global_kpi["sla"] < 0.8:
        dynamic_recs.append("Incrementar cobertura intradia en ventanas con SLA bajo y reforzar ruteo prioritario.")
    if global_kpi["abandono"] > 0.08:
        dynamic_recs.append("Activar plan antiabandono: callback, overflow y redistribucion de breaks en picos.")
    if mape > 0.2:
        dynamic_recs.append("Mejorar forecasting: usar ajuste semanal + estacionalidad para reducir error de demanda.")
    if worst_hour and worst_hour.get("risk_score", 0) > 0:
        dynamic_recs.append(f"Aplicar accion inmediata en franja {int(worst_hour['hora']):02d}:00: micro-shifts y skill rebalancing.")
    if not dynamic_recs:
        dynamic_recs.append("Operacion estable: mantener monitoreo en tiempo real y revisiones semanales.")

    return {
        "global": global_kpi,
        "critical_day": critical_day,
        "peak_hour": peak_hour,
        "by_month": by_month,
        "by_week": by_week,
        "by_day": by_day_named,
        "by_hour": hour_kpi,
        "mape_weekly_calls": mape,
        "alerts": alerts,
        "worst_week": worst_week,
        "worst_day": worst_day,
        "worst_hour": worst_hour,
        "dynamic_recommendations": dynamic_recs,
    }


def render_result_box(title: str, value: str) -> None:
    st.markdown(
        f"""
        <div style="border:2px solid #16a34a;padding:12px;border-radius:10px;background:#f0fdf4;">
            <div style="font-size:12px;color:#166534;font-weight:600;">RESULTADO</div>
            <div style="font-size:16px;color:#14532d;font-weight:700;">{title}: {value}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def recs_ex1(r1: dict, ex1: dict) -> list[str]:
    recs = []
    if r1["inbound_aht_sec"] > 360:
        recs.append("AHT alto: revisar tipificaciones y reducir tiempos de ACW.")
    if ex1["inbound_availtime"] > 0.1:
        recs.append("Availtime alto: redistribuir carga para subir ocupacion productiva.")
    if ex1["nda"] < 0.9:
        recs.append("NDA bajo: reforzar cobertura en horas pico y monitoreo intradia.")
    if not recs:
        recs.append("Resultado estable: mantener monitoreo y control por intervalos.")
    return recs


def recs_ex2(r2: dict, ex2: dict) -> list[str]:
    recs = []
    ratio = (r2["scheduled_hours"] / r2["attended_hours"]) if r2["attended_hours"] else 0
    if ex2["vacations"] > 0.05:
        recs.append("Vacaciones elevadas: planificar reemplazos para proteger horas programadas.")
    if ratio > 1.08:
        recs.append("Brecha alta entre horas presentes y programadas: ajustar mix FT/PT.")
    if ex2["inbound_occupancy"] < 0.8:
        recs.append("Ocupacion baja: revisar sobre-dotacion o reasignar tareas de soporte.")
    if not recs:
        recs.append("Estructura balanceada: continuar seguimiento semanal de capacidad.")
    return recs


def recs_ex3(r3: dict) -> list[str]:
    recs = []
    shifts = r3.get("shifts", [])
    if not shifts:
        return ["Sin turnos cargados para analizar."]
    max_aht = max((float(s.get("aht_sec", 0)) for s in shifts), default=0)
    min_aht = min((float(s.get("aht_sec", 0)) for s in shifts), default=0)
    if max_aht > 420:
        recs.append("Hay turnos con AHT alto: aplicar coaching focalizado por turno.")
    if (max_aht - min_aht) > 120:
        recs.append("Variacion alta entre turnos: estandarizar procesos y guiones.")
    if float(r3.get("global_aht_sec", 0)) > 320:
        recs.append("AHT global elevado: simplificar flujo operativo y tareas post-llamada.")
    if not recs:
        recs.append("Comportamiento estable entre turnos: mantener controles actuales.")
    return recs


st.set_page_config(page_title="WFM Tools", layout="wide")
st.title("WFM Tools")
st.caption("Suite de calculadoras y analitica operativa para planificacion y gestion WFM.")
st.info(
    "Estas calculadoras te permiten estimar rapidamente AHT, horas requeridas, capacidad por turnos y "
    "dimensionamiento diario. Con los resultados puedes tomar decisiones de staffing, cobertura y eficiencia operativa."
)

if "payload" not in st.session_state:
    st.session_state.payload = load_defaults()

if st.button("Restaurar valores default"):
    st.session_state.payload = load_defaults()

payload = deepcopy(st.session_state.payload)
tab_ex, tab_dim, tab_case = st.tabs(["Ejercicios", "Dimensionado", "Caso de Estudio"])

with tab_ex:
    ex1 = payload["exercises"]["exercise1"]
    ex2 = payload["exercises"]["exercise2"]
    ex3 = payload["exercises"]["exercise3"]
    ex3["shifts"] = sanitize_shifts(ex3.get("shifts", []))

    results = calculate_exercises(payload["exercises"])
    r1 = results["exercise1"]
    r2 = results["exercise2"]
    r3 = results["exercise3"]

    st.markdown("### Calculadora 1 - AHT Inbound")
    left, right = st.columns(2)
    with left:
        ex1_table = editable_sheet(
            "Entradas",
            [
                {"Campo": "Horas Programadas (Scheduled Hours)", "Valor": float(ex1["scheduled_hours"])},
                {"Campo": "Ausentismo (Absenteeism %)", "Valor": float(ex1["absenteeism"]) * 100},
                {"Campo": "Auxiliares (Auxiliaries %)", "Valor": float(ex1["auxiliaries"]) * 100},
                {"Campo": "Tiempo Disponible Inbound (Inbound Availtime %)", "Valor": float(ex1["inbound_availtime"]) * 100},
                {"Campo": "Nivel de Atencion (NDA %)", "Valor": float(ex1["nda"]) * 100},
                {"Campo": "Llamadas (Calls)", "Valor": float(ex1["calls"])},
            ],
            "ex1_sheet",
        )
        ex1["scheduled_hours"] = float(ex1_table.loc[0, "Valor"])
        ex1["absenteeism"] = float(ex1_table.loc[1, "Valor"]) / 100
        ex1["auxiliaries"] = float(ex1_table.loc[2, "Valor"]) / 100
        ex1["inbound_availtime"] = float(ex1_table.loc[3, "Valor"]) / 100
        ex1["nda"] = float(ex1_table.loc[4, "Valor"]) / 100
        ex1["calls"] = float(ex1_table.loc[5, "Valor"])
    with right:
        results = calculate_exercises(payload["exercises"])
        r1 = results["exercise1"]
        render_result_box("AHT Inbound (sec)", n(r1["inbound_aht_sec"]))
        st.table(
            pd.DataFrame(
                [
                    {"Paso": "Horas presentes", "Resultado": n(r1["attendance_hours"])},
                    {"Paso": "Horas productivas", "Resultado": n(r1["productive_hours"])},
                    {"Paso": "Ocupacion", "Resultado": p(r1["occupancy"])},
                    {"Paso": "Horas transaccionales", "Resultado": n(r1["transactional_hours"])},
                    {"Paso": "Llamadas atendidas", "Resultado": n(r1["answered_calls"])},
                ]
            )
        )
        st.markdown("**Recomendaciones dinamicas**")
        for rec in recs_ex1(r1, ex1):
            st.write(f"- {rec}")

    st.markdown("### Calculadora 2 - Horas Presentes y Programadas")
    left, right = st.columns(2)
    with left:
        ex2_table = editable_sheet(
            "Entradas",
            [
                {"Campo": "Inbound AHT (seg)", "Valor": float(ex2["inbound_aht_sec"])},
                {"Campo": "Llamadas (Calls)", "Valor": float(ex2["calls"])},
                {"Campo": "Nivel de Atencion (NDA %)", "Valor": float(ex2["nda"]) * 100},
                {"Campo": "Ocupacion Inbound (Inbound Occupancy %)", "Valor": float(ex2["inbound_occupancy"]) * 100},
                {"Campo": "Horas Productivas Back Office (Backoffice Productive Hours)", "Valor": float(ex2["productive_hours_backoffice"])},
                {"Campo": "Horas Productivas Email (Email Productive Hours)", "Valor": float(ex2["productive_hours_email"])},
                {"Campo": "Vacaciones (Vacations %)", "Valor": float(ex2["vacations"]) * 100},
                {"Campo": "Horas Auxiliares (Auxiliary Hours)", "Valor": float(ex2["auxiliary_hours"])},
            ],
            "ex2_sheet",
        )
        ex2["inbound_aht_sec"] = float(ex2_table.loc[0, "Valor"])
        ex2["calls"] = float(ex2_table.loc[1, "Valor"])
        ex2["nda"] = float(ex2_table.loc[2, "Valor"]) / 100
        ex2["inbound_occupancy"] = float(ex2_table.loc[3, "Valor"]) / 100
        ex2["productive_hours_backoffice"] = float(ex2_table.loc[4, "Valor"])
        ex2["productive_hours_email"] = float(ex2_table.loc[5, "Valor"])
        ex2["vacations"] = float(ex2_table.loc[6, "Valor"]) / 100
        ex2["auxiliary_hours"] = float(ex2_table.loc[7, "Valor"])
    with right:
        results = calculate_exercises(payload["exercises"])
        r2 = results["exercise2"]
        render_result_box("Horas presentes (Attendance Hours)", n(r2["attended_hours"]))
        render_result_box("Horas programadas requeridas (Required Scheduled Hours)", n(r2["scheduled_hours"]))
        st.table(
            pd.DataFrame(
                [
                    {"Paso": "Llamadas atendidas", "Resultado": n(r2["answered_calls"])},
                    {"Paso": "Horas transaccionales inbound", "Resultado": n(r2["inbound_transactional_hours"])},
                    {"Paso": "Horas productivas inbound", "Resultado": n(r2["inbound_productive_hours"])},
                    {"Paso": "Horas productivas totales", "Resultado": n(r2["total_productive_hours"])},
                ]
            )
        )
        st.markdown("**Recomendaciones dinamicas**")
        for rec in recs_ex2(r2, ex2):
            st.write(f"- {rec}")

    st.markdown("### Calculadora 3 - AHT por Turno")
    left, right = st.columns(2)
    with left:
        st.markdown("#### Entradas")
        shifts_df = pd.DataFrame(ex3["shifts"])
        edited_shifts = st.data_editor(shifts_df, num_rows="dynamic", use_container_width=True, key="ex3_sheet")
        ex3["shifts"] = sanitize_shifts(edited_shifts.to_dict(orient="records"))
    with right:
        results = calculate_exercises(payload["exercises"])
        r3 = results["exercise3"]
        render_result_box("AHT global de turnos (Global Shift AHT sec)", n(r3["global_aht_sec"]))
        st.dataframe(pd.DataFrame(r3["shifts"]), use_container_width=True)
        st.markdown("**Recomendaciones dinamicas**")
        for rec in recs_ex3(r3):
            st.write(f"- {rec}")

with tab_dim:
    dim = payload["dimensioning"]
    st.markdown("### Calculadora 4 - Dimensionado Diario")
    dim_table = editable_sheet(
        "Entradas del caso",
        [
            {"Campo": "Total de llamadas semanal (Weekly Calls)", "Valor": float(dim["weekly_calls"])},
            {"Campo": "% Part-Time a contratar (Part-Time Ratio %)", "Valor": float(dim["part_time_ratio"]) * 100},
        ],
        "dim_sheet",
    )
    dim["weekly_calls"] = float(dim_table.loc[0, "Valor"])
    dim["part_time_ratio"] = float(dim_table.loc[1, "Valor"]) / 100

    st.markdown("#### Distribucion diaria")
    days_df = pd.DataFrame(dim["days"])
    edited_days = st.data_editor(days_df, num_rows="dynamic", use_container_width=True, key="days_sheet")
    dim["days"] = edited_days.to_dict(orient="records")

    st.markdown("#### Premisas fijas de calculo")
    st.table(
        pd.DataFrame(
            [
                {"Premisa": "AHT (sec)", "Valor": dim["aht_sec"]},
                {"Premisa": "Ausentismo (%)", "Valor": f"{dim['absenteeism'] * 100:.2f}%"},
                {"Premisa": "Auxiliares (%)", "Valor": f"{dim['auxiliaries'] * 100:.2f}%"},
                {"Premisa": "Ocupacion objetivo (%)", "Valor": f"{dim['occupancy_target'] * 100:.2f}%"},
                {"Premisa": "SLA", "Valor": f"{int(dim['sla_level']*100)}/{int(dim['sla_time_sec'])}"},
                {"Premisa": "Horas FT/PT", "Valor": f"{dim['ft_hours_week']}/{dim['pt_hours_week']}"},
            ]
        )
    )

    dim_result = calculate_dimensioning(dim)
    st.markdown("### Resultado detallado por dia")
    st.info("Pregunta: Calcule agentes requeridos por dia (HC + shrinkage), FTE y modelo FT/PT.")
    st.dataframe(pd.DataFrame(dim_result["rows"]), use_container_width=True)

    st.markdown("### Modelo de contratacion")
    mix = dim_result["contract_model"]["ft_pt_mix"]
    solo = dim_result["contract_model"]["solo_ft"]
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        render_result_box("HC pico requerido", f"{int(mix['hc_peak_required'])}")
    with c2:
        render_result_box("Part-Time Ratio", p(float(mix["part_time_ratio"])))
    with c3:
        render_result_box("FTE total (Mix FT/PT)", n(float(mix["fte_total"])))
    with c4:
        render_result_box("Ahorro FTE vs Solo FT", n(float(dim_result["contract_model"]["fte_saving"])))

    st.markdown("#### Resumen de indicadores clave")
    st.table(
        pd.DataFrame(
            [
                {"Indicador": "Shrinkage", "Valor": p(dim_result["assumptions"]["shrinkage"] - 1)},
                {"Indicador": "Ocupacion objetivo", "Valor": p(dim_result["assumptions"]["occupancy_target"])},
                {"Indicador": "SLA objetivo", "Valor": f"{int(dim_result['assumptions']['sla_level']*100)}/{int(dim_result['assumptions']['sla_time_sec'])}"},
                {"Indicador": "Part-Time Ratio", "Valor": p(float(mix["part_time_ratio"]))},
                {"Indicador": "FTE Saving %", "Valor": p(float(dim_result["contract_model"]["fte_saving_pct"]))},
                {"Indicador": "FT personas", "Valor": int(mix["ft_people"])},
                {"Indicador": "PT personas", "Valor": int(mix["pt_people"])},
                {"Indicador": "Total personas", "Valor": int(mix["total_people"])},
            ]
        )
    )
    st.table(pd.DataFrame([solo, mix]))

with tab_case:
    st.markdown(
        """
        <style>
        .risk-card {border-radius:14px;padding:12px 14px;background:linear-gradient(135deg,#0f172a,#1e293b);color:#e2e8f0;border:1px solid #334155;}
        .risk-title {font-size:12px;opacity:.85;text-transform:uppercase;letter-spacing:.06em;}
        .risk-value {font-size:20px;font-weight:800;margin-top:4px;}
        .risk-chip-high {display:inline-block;padding:4px 8px;border-radius:999px;background:#7f1d1d;color:#fecaca;font-weight:700;font-size:12px;}
        .risk-chip-med {display:inline-block;padding:4px 8px;border-radius:999px;background:#78350f;color:#fde68a;font-weight:700;font-size:12px;}
        .risk-chip-low {display:inline-block;padding:4px 8px;border-radius:999px;background:#14532d;color:#bbf7d0;font-weight:700;font-size:12px;}
        </style>
        """,
        unsafe_allow_html=True,
    )
    st.markdown("### Caso de Estudio Operativo")
    st.write(
        "Analiza indicadores de gestion de llamadas, explica la situacion actual del servicio "
        "y propone sugerencias de optimizacion."
    )

    kpi = case_study_kpis()
    g = kpi["global"]
    st.markdown("### KPIs Globales")
    st.markdown(
        """
        <style>
        [data-testid="stMetricValue"] {font-size: 1.05rem !important; line-height: 1.1 !important;}
        [data-testid="stMetricLabel"] {font-size: 0.78rem !important;}
        div[data-testid="stMetric"] {padding: 6px 8px !important;}
        </style>
        """,
        unsafe_allow_html=True,
    )
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Recibidas", f"{g['recibidas']:,.0f}")
    c2.metric("Atendidas", f"{g['atendidas']:,.0f}")
    c3.metric("Abandonadas", f"{g['abandonadas']:,.0f}")
    c4.metric("Dentro SLA", f"{(g['sla']*g['atendidas']):,.0f}")
    c5.metric("Answer Rate", p(g["atendidas"] / g["recibidas"] if g["recibidas"] else 0))
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Abandono", p(g["abandono"]))
    c2.metric("SLA", p(g["sla"]))
    c3.metric("AHT (seg)", n(g["aht"]))
    c4.metric("ASA (seg)", n(g["asa"]))

    st.markdown("### Alertas y Desviaciones")
    a1, a2 = st.columns([1, 3])
    a1.metric("MAPE", p(kpi["mape_weekly_calls"]))
    with a2:
        st.caption("Error porcentual medio semanal de llamadas (variabilidad de demanda).")
    for alert in kpi["alerts"]:
        st.warning(alert)

    def risk_chip(score: float) -> str:
        if score >= 20:
            return '<span class="risk-chip-high">Riesgo Alto</span>'
        if score >= 8:
            return '<span class="risk-chip-med">Riesgo Medio</span>'
        return '<span class="risk-chip-low">Riesgo Bajo</span>'

    wweek = kpi.get("worst_week", {})
    wday = kpi.get("worst_day", {})
    whour = kpi.get("worst_hour", {})

    st.markdown("### Radar de Desviaciones Criticas")
    rc1, rc2, rc3 = st.columns(3)
    with rc1:
        score = float(wweek.get("risk_score", 0) or 0)
        st.markdown(
            f"""<div class="risk-card"><div class="risk-title">Semana con mayor desviacion</div>
            <div class="risk-value">{wweek.get('semana', 'N/A')}</div>{risk_chip(score)}
            <div style="margin-top:8px;font-size:12px;">Score: {score:.2f}</div></div>""",
            unsafe_allow_html=True,
        )
    with rc2:
        score = float(wday.get("risk_score", 0) or 0)
        st.markdown(
            f"""<div class="risk-card"><div class="risk-title">Dia mas critico</div>
            <div class="risk-value">{wday.get('dia', 'N/A')}</div>{risk_chip(score)}
            <div style="margin-top:8px;font-size:12px;">Score: {score:.2f}</div></div>""",
            unsafe_allow_html=True,
        )
    with rc3:
        score = float(whour.get("risk_score", 0) or 0)
        hour_label = f"{int(whour.get('hora', 0)):02d}:00" if whour else "N/A"
        st.markdown(
            f"""<div class="risk-card"><div class="risk-title">Franja critica</div>
            <div class="risk-value">{hour_label}</div>{risk_chip(score)}
            <div style="margin-top:8px;font-size:12px;">Score: {score:.2f}</div></div>""",
            unsafe_allow_html=True,
        )

    st.markdown("### Analisis por Mes")
    month_df = kpi["by_month"][["label", "recibidas", "atendidas", "abandonadas", "sla", "abandon_rate"]].rename(columns={"label": "Mes", "sla": "SLA", "abandon_rate": "Abandono"})
    st.dataframe(style_deviation_table(month_df), use_container_width=True)
    month_chart = kpi["by_month"].set_index("label")[["recibidas", "atendidas"]]
    month_chart["sla_gap"] = (0.8 - kpi["by_month"].set_index("label")["sla"]).clip(lower=0)
    st.line_chart(month_chart)
    st.caption("Desvio SLA (sla_gap): cuanto falta para llegar al objetivo 80%.")

    st.markdown("### Analisis por Semana")
    week_df = kpi["by_week"][["semana", "recibidas", "atendidas", "abandonadas", "sla", "abandon_rate"]].rename(columns={"semana": "Semana", "sla": "SLA", "abandon_rate": "Abandono"})
    st.dataframe(style_deviation_table(week_df), use_container_width=True)
    week_chart = kpi["by_week"].set_index("semana")[["recibidas", "atendidas"]]
    week_chart["sla_gap"] = (0.8 - kpi["by_week"].set_index("semana")["sla"]).clip(lower=0)
    week_chart["abandon_gap"] = (kpi["by_week"].set_index("semana")["abandon_rate"] - 0.08).clip(lower=0)
    st.line_chart(week_chart)
    st.caption("Desvios semanales: sla_gap (>0 indica SLA bajo objetivo), abandon_gap (>0 indica abandono sobre 8%).")

    st.markdown("### Analisis por Dia de Semana")
    day_df = kpi["by_day"][["dia", "recibidas", "atendidas", "abandonada", "sla", "abandon_rate"]].rename(columns={"dia": "Dia", "abandonada": "abandonadas", "sla": "SLA", "abandon_rate": "Abandono"})
    st.dataframe(style_deviation_table(day_df), use_container_width=True)
    day_chart = kpi["by_day"].set_index("dia")[["recibidas", "atendidas"]]
    day_chart["sla_gap"] = (0.8 - kpi["by_day"].set_index("dia")["sla"]).clip(lower=0)
    st.bar_chart(day_chart)
    st.caption("Dias con mayor sla_gap requieren refuerzo de cobertura.")

    st.markdown("### Analisis por Franja Horaria")
    hour_df = kpi["by_hour"][["franja", "recibidas", "atendidas", "abandonadas", "sla", "abandon_rate"]].rename(columns={"franja": "Franja Horaria", "sla": "SLA", "abandon_rate": "Abandono"})
    st.dataframe(style_deviation_table(hour_df), use_container_width=True)
    hour_chart = kpi["by_hour"].set_index("franja")[["recibidas", "atendidas"]]
    hour_chart["sla_gap"] = (0.8 - kpi["by_hour"].set_index("franja")["sla"]).clip(lower=0)
    hour_chart["abandon_gap"] = (kpi["by_hour"].set_index("franja")["abandon_rate"] - 0.08).clip(lower=0)
    st.area_chart(hour_chart)
    st.caption("Franjas con mayor sla_gap y abandon_gap son prioridad de accion intradia.")

    st.markdown("### Recomendaciones Dinamicas")
    for i, rec in enumerate(kpi.get("dynamic_recommendations", []), start=1):
        st.write(f"{i}. {rec}")

st.session_state.payload = payload

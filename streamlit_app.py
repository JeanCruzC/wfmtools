from __future__ import annotations

import json
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


def editable_sheet(title: str, rows: list[dict], key: str) -> pd.DataFrame:
    st.markdown(f"#### {title}")
    df = pd.DataFrame(rows)
    return st.data_editor(df, use_container_width=True, hide_index=True, key=key)


def case_study_kpis() -> dict:
    df = pd.read_csv(RECORDS_FILE)
    received = float(df["Recibidas"].sum())
    answered = float(df["Atendidas"].sum())
    abandoned = float(df["abandonada"].sum())
    sla_ans = float(df["Atendidas dentro de SLA"].sum())
    weighted_aht = float((df["AHT_Seg"] * df["Atendidas"]).sum())
    weighted_tme = float((df["TME_Seg"] * df["Atendidas"]).sum())

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
        df.groupby("DiaSem", as_index=False)
        .agg({"Recibidas": "sum", "Atendidas": "sum", "abandonada": "sum", "Atendidas dentro de SLA": "sum"})
        .rename(columns={"Atendidas dentro de SLA": "sla_ans"})
    )
    by_day["sla"] = by_day["sla_ans"] / by_day["Atendidas"].replace(0, 1)
    critical_day = by_day.sort_values("sla").iloc[0].to_dict()

    by_hour = df.groupby("hora", as_index=False).agg({"Recibidas": "sum"}).sort_values("Recibidas", ascending=False)
    peak_hour = by_hour.iloc[0].to_dict()

    return {"global": global_kpi, "critical_day": critical_day, "peak_hour": peak_hour}


st.set_page_config(page_title="WFM Planeamiento - Streamlit", layout="wide")
st.title("WFM Planeamiento - Formato Tipo Excel")
st.caption("Calculadoras de planeamiento WFM con entradas simples y solucion detallada.")

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
                {"Campo": "Horas Programadas", "Valor": float(ex1["scheduled_hours"])},
                {"Campo": "Ausentismo (%)", "Valor": float(ex1["absenteeism"]) * 100},
                {"Campo": "Auxiliares (%)", "Valor": float(ex1["auxiliaries"]) * 100},
                {"Campo": "Inbound Availtime (%)", "Valor": float(ex1["inbound_availtime"]) * 100},
                {"Campo": "NDA (%)", "Valor": float(ex1["nda"]) * 100},
                {"Campo": "Llamadas", "Valor": float(ex1["calls"])},
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
        st.metric("Resultado AHT Inbound (seg)", n(r1["inbound_aht_sec"]))
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

    st.markdown("### Calculadora 2 - Horas Presentes y Programadas")
    left, right = st.columns(2)
    with left:
        ex2_table = editable_sheet(
            "Entradas",
            [
                {"Campo": "Inbound AHT (seg)", "Valor": float(ex2["inbound_aht_sec"])},
                {"Campo": "Llamadas", "Valor": float(ex2["calls"])},
                {"Campo": "NDA (%)", "Valor": float(ex2["nda"]) * 100},
                {"Campo": "Ocupacion Inbound (%)", "Valor": float(ex2["inbound_occupancy"]) * 100},
                {"Campo": "Hrs Productivas Back Office", "Valor": float(ex2["productive_hours_backoffice"])},
                {"Campo": "Hrs Productivas Email", "Valor": float(ex2["productive_hours_email"])},
                {"Campo": "Vacaciones (%)", "Valor": float(ex2["vacations"]) * 100},
                {"Campo": "Auxiliares (hrs)", "Valor": float(ex2["auxiliary_hours"])},
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
        st.metric("Horas presentes", n(r2["attended_hours"]))
        st.metric("Horas programadas requeridas", n(r2["scheduled_hours"]))
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

    st.markdown("### Calculadora 3 - AHT por Turno")
    left, right = st.columns(2)
    with left:
        st.markdown("#### Entradas")
        shifts_df = pd.DataFrame(ex3["shifts"])
        edited_shifts = st.data_editor(shifts_df, num_rows="dynamic", use_container_width=True, key="ex3_sheet")
        ex3["shifts"] = edited_shifts.to_dict(orient="records")
    with right:
        results = calculate_exercises(payload["exercises"])
        r3 = results["exercise3"]
        st.metric("AHT global de turnos (seg)", n(r3["global_aht_sec"]))
        st.dataframe(pd.DataFrame(r3["shifts"]), use_container_width=True)

with tab_dim:
    dim = payload["dimensioning"]
    dim_table = editable_sheet(
        "Supuestos de Dimensionado",
        [
            {"Campo": "Llamadas semanales", "Valor": float(dim["weekly_calls"])},
            {"Campo": "AHT (seg)", "Valor": float(dim["aht_sec"])},
            {"Campo": "Ausentismo (%)", "Valor": float(dim["absenteeism"]) * 100},
            {"Campo": "Auxiliares (%)", "Valor": float(dim["auxiliaries"]) * 100},
            {"Campo": "Ocupacion objetivo (%)", "Valor": float(dim["occupancy_target"]) * 100},
            {"Campo": "SLA tiempo (seg)", "Valor": float(dim["sla_time_sec"])},
            {"Campo": "SLA nivel (%)", "Valor": float(dim["sla_level"]) * 100},
            {"Campo": "Horas FT/sem", "Valor": float(dim["ft_hours_week"])},
            {"Campo": "Horas PT/sem", "Valor": float(dim["pt_hours_week"])},
            {"Campo": "Ratio PT (%)", "Valor": float(dim["part_time_ratio"]) * 100},
        ],
        "dim_sheet",
    )

    dim["weekly_calls"] = float(dim_table.loc[0, "Valor"])
    dim["aht_sec"] = float(dim_table.loc[1, "Valor"])
    dim["absenteeism"] = float(dim_table.loc[2, "Valor"]) / 100
    dim["auxiliaries"] = float(dim_table.loc[3, "Valor"]) / 100
    dim["occupancy_target"] = float(dim_table.loc[4, "Valor"]) / 100
    dim["sla_time_sec"] = float(dim_table.loc[5, "Valor"])
    dim["sla_level"] = float(dim_table.loc[6, "Valor"]) / 100
    dim["ft_hours_week"] = float(dim_table.loc[7, "Valor"])
    dim["pt_hours_week"] = float(dim_table.loc[8, "Valor"])
    dim["part_time_ratio"] = float(dim_table.loc[9, "Valor"]) / 100

    st.markdown("#### Distribucion diaria")
    days_df = pd.DataFrame(dim["days"])
    edited_days = st.data_editor(days_df, num_rows="dynamic", use_container_width=True, key="days_sheet")
    dim["days"] = edited_days.to_dict(orient="records")

    dim_result = calculate_dimensioning(dim)
    st.markdown("### Resultado detallado por dia")
    st.info("Pregunta: Calcule agentes requeridos por dia (HC + shrinkage), FTE y modelo FT/PT.")
    st.dataframe(pd.DataFrame(dim_result["rows"]), use_container_width=True)

    st.markdown("### Modelo de contratacion")
    st.table(pd.DataFrame([dim_result["contract_model"]["solo_ft"], dim_result["contract_model"]["ft_pt_mix"]]))

with tab_case:
    st.markdown("### Caso de Estudio Operativo")
    st.write(
        "Analiza indicadores de gestion de llamadas, explica la situacion actual del servicio "
        "y propone sugerencias de optimizacion."
    )

    kpi = case_study_kpis()
    g = kpi["global"]
    st.markdown("### Resultado calculado con los datos operativos")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("SLA Global", p(g["sla"]))
    c2.metric("Abandono Global", p(g["abandono"]))
    c3.metric("AHT Ponderado (seg)", n(g["aht"]))
    c4.metric("ASA (seg)", n(g["asa"]))

    st.markdown("### Hallazgos automaticos")
    st.write(f"- Dia critico por SLA (DiaSem): **{int(kpi['critical_day']['DiaSem'])}**")
    st.write(f"- Hora pico por recibidas: **{int(kpi['peak_hour']['hora']):02d}:00**")
    st.write("- Recomendacion: revisar cobertura por intervalo en horas pico y reforzar control de abandono/SLA.")

    st.markdown("### Resumen interpretativo")
    st.write(
        "Al nivel global se identifica un SLA por debajo del objetivo 80/20. "
        "Los dias criticos concentran mayor riesgo de abandono y menor SLA, por lo que se recomienda ajustar "
        "dotacion y control operativo por intervalos."
    )

st.session_state.payload = payload

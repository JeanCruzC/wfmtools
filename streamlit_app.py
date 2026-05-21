from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

import pandas as pd
import streamlit as st

from backend.app.calculations import calculate_dimensioning, calculate_exercises

DATA_FILE = Path(__file__).resolve().parent / "data" / "example_inputs.json"


def load_defaults() -> dict:
    return json.loads(DATA_FILE.read_text(encoding="utf-8"))


def pct_input(label: str, value: float, key: str) -> float:
    pct_value = st.number_input(label, min_value=0.0, max_value=100.0, value=float(value) * 100, key=key)
    return pct_value / 100.0


st.set_page_config(page_title="WFM Planeamiento - Streamlit", layout="wide")
st.title("WFM Planeamiento - Streamlit")
st.caption("Version ligera para desplegar rapido en Streamlit usando los mismos calculos del proyecto.")

if "payload" not in st.session_state:
    st.session_state.payload = load_defaults()

if st.button("Restaurar valores default"):
    st.session_state.payload = load_defaults()

payload = deepcopy(st.session_state.payload)
tab_ex, tab_dim = st.tabs(["Ejercicios", "Dimensionado"])

with tab_ex:
    st.subheader("Ejercicio 1")
    ex1 = payload["exercises"]["exercise1"]
    c1, c2, c3 = st.columns(3)
    ex1["scheduled_hours"] = c1.number_input("Scheduled hours", min_value=0.0, value=float(ex1["scheduled_hours"]))
    ex1["calls"] = c2.number_input("Calls", min_value=0.0, value=float(ex1["calls"]))
    ex1["nda"] = pct_input("NDA (%)", ex1["nda"], "ex1_nda")
    ex1["absenteeism"] = pct_input("Absenteeism (%)", ex1["absenteeism"], "ex1_abs")
    ex1["auxiliaries"] = pct_input("Auxiliaries (%)", ex1["auxiliaries"], "ex1_aux")
    ex1["inbound_availtime"] = pct_input("Inbound availtime (%)", ex1["inbound_availtime"], "ex1_av")

    st.subheader("Ejercicio 2")
    ex2 = payload["exercises"]["exercise2"]
    c1, c2, c3 = st.columns(3)
    ex2["inbound_aht_sec"] = c1.number_input("Inbound AHT (seg)", min_value=0.0, value=float(ex2["inbound_aht_sec"]))
    ex2["calls"] = c2.number_input("Calls (E2)", min_value=0.0, value=float(ex2["calls"]))
    ex2["nda"] = pct_input("NDA E2 (%)", ex2["nda"], "ex2_nda")
    ex2["inbound_occupancy"] = pct_input("Inbound occupancy (%)", ex2["inbound_occupancy"], "ex2_occ")
    ex2["productive_hours_backoffice"] = c3.number_input(
        "Backoffice productive hours", min_value=0.0, value=float(ex2["productive_hours_backoffice"])
    )
    ex2["productive_hours_email"] = c1.number_input(
        "Email productive hours", min_value=0.0, value=float(ex2["productive_hours_email"])
    )
    ex2["vacations"] = pct_input("Vacations (%)", ex2["vacations"], "ex2_vac")
    ex2["auxiliary_hours"] = c2.number_input("Auxiliary hours", min_value=0.0, value=float(ex2["auxiliary_hours"]))

    st.subheader("Ejercicio 3")
    ex3 = payload["exercises"]["exercise3"]
    shifts_df = pd.DataFrame(ex3["shifts"])
    edited_shifts = st.data_editor(shifts_df, num_rows="dynamic", use_container_width=True)
    ex3["shifts"] = edited_shifts.to_dict(orient="records")

    exercises_result = calculate_exercises(payload["exercises"])
    st.subheader("Resultados")
    r1 = exercises_result["exercise1"]
    r2 = exercises_result["exercise2"]
    r3 = exercises_result["exercise3"]

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("AHT inbound (seg)", f"{r1['inbound_aht_sec']:.3f}")
    k2.metric("Horas presentes", f"{r1['attendance_hours']:.3f}")
    k3.metric("Horas programadas req.", f"{r2['scheduled_hours']:.3f}")
    k4.metric("AHT global turnos (seg)", f"{r3['global_aht_sec']:.3f}")

    st.dataframe(pd.DataFrame(r3["shifts"]), use_container_width=True)

with tab_dim:
    st.subheader("Supuestos de Dimensionado")
    dim = payload["dimensioning"]
    c1, c2, c3 = st.columns(3)
    dim["weekly_calls"] = c1.number_input("Weekly calls", min_value=0.0, value=float(dim["weekly_calls"]))
    dim["aht_sec"] = c2.number_input("AHT (seg)", min_value=0.0, value=float(dim["aht_sec"]))
    dim["occupancy_target"] = pct_input("Occupancy target (%)", dim["occupancy_target"], "dim_occ")
    dim["absenteeism"] = pct_input("Absenteeism (%)", dim["absenteeism"], "dim_abs")
    dim["auxiliaries"] = pct_input("Auxiliaries (%)", dim["auxiliaries"], "dim_aux")
    dim["sla_level"] = pct_input("SLA level (%)", dim["sla_level"], "dim_sla")
    dim["sla_time_sec"] = c3.number_input("SLA time (seg)", min_value=0.0, value=float(dim["sla_time_sec"]))
    dim["part_time_ratio"] = pct_input("Part-time ratio (%)", dim["part_time_ratio"], "dim_pt")
    dim["ft_hours_week"] = c1.number_input("FT hours/week", min_value=1.0, value=float(dim["ft_hours_week"]))
    dim["pt_hours_week"] = c2.number_input("PT hours/week", min_value=1.0, value=float(dim["pt_hours_week"]))

    days_df = pd.DataFrame(dim["days"])
    edited_days = st.data_editor(days_df, num_rows="dynamic", use_container_width=True)
    dim["days"] = edited_days.to_dict(orient="records")

    dim_result = calculate_dimensioning(dim)
    rows_df = pd.DataFrame(dim_result["rows"])
    st.subheader("Resultado diario")
    st.dataframe(rows_df, use_container_width=True)

    mix = dim_result["contract_model"]["ft_pt_mix"]
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("HC pico req.", int(mix["hc_peak_required"]))
    c2.metric("FT personas", int(mix["ft_people"]))
    c3.metric("PT personas", int(mix["pt_people"]))
    c4.metric("FTE total", f"{mix['fte_total']:.2f}")

st.session_state.payload = payload

from __future__ import annotations

import math
from typing import Any


def safe_div(numerator: float, denominator: float) -> float:
    return float(numerator) / float(denominator) if denominator else 0.0


def round_up(value: float) -> int:
    return int(math.ceil(value))


def erlang_c_probability_wait(traffic_erlang: float, agents: int) -> float:
    """Probabilidad de espera Erlang C.

    Se calcula con Erlang B recursivo para evitar overflow con tráficos altos.
    Devuelve 1.0 si el sistema está inestable.
    """
    if traffic_erlang <= 0:
        return 0.0
    if agents <= traffic_erlang:
        return 1.0

    # Erlang B estable: B_n = (A * B_{n-1}) / (n + A * B_{n-1})
    erlang_b = 1.0
    for n in range(1, agents + 1):
        erlang_b = (traffic_erlang * erlang_b) / (n + traffic_erlang * erlang_b)

    rho = traffic_erlang / agents
    return erlang_b / (1 - rho + rho * erlang_b)


def erlang_c_service_level(
    traffic_erlang: float,
    agents: int,
    target_seconds: float,
    aht_seconds: float,
) -> float:
    if traffic_erlang <= 0 or agents <= 0 or aht_seconds <= 0:
        return 1.0
    if agents <= traffic_erlang:
        return 0.0
    pw = erlang_c_probability_wait(traffic_erlang, agents)
    exponent = -((agents - traffic_erlang) * (target_seconds / aht_seconds))
    return 1 - pw * math.exp(exponent)


def erlang_c_required_agents(
    traffic_erlang: float,
    aht_seconds: float,
    target_seconds: float,
    target_service_level: float,
    max_agents: int = 5000,
) -> int:
    if traffic_erlang <= 0:
        return 0
    start = max(1, math.floor(traffic_erlang) + 1)
    for agents in range(start, max_agents + 1):
        if erlang_c_service_level(traffic_erlang, agents, target_seconds, aht_seconds) >= target_service_level:
            return agents
    return max_agents


def calculate_exercises(payload: dict[str, Any]) -> dict[str, Any]:
    ex1 = payload.get("exercise1", {})
    ex2 = payload.get("exercise2", {})
    ex3 = payload.get("exercise3", {})

    scheduled_hours = float(ex1.get("scheduled_hours", 0))
    absenteeism = float(ex1.get("absenteeism", 0))
    auxiliaries = float(ex1.get("auxiliaries", 0))
    inbound_availtime = float(ex1.get("inbound_availtime", 0))
    nda = float(ex1.get("nda", 0))
    calls = float(ex1.get("calls", 0))

    attendance_hours = scheduled_hours * (1 - absenteeism)
    productive_hours = attendance_hours * (1 - auxiliaries)
    occ = 1 - inbound_availtime
    transactional_hours = productive_hours * occ
    answered_calls = calls * nda
    inbound_aht_sec = safe_div(transactional_hours * 3600, answered_calls)

    inbound_aht2 = float(ex2.get("inbound_aht_sec", 0))
    calls2 = float(ex2.get("calls", 0))
    nda2 = float(ex2.get("nda", 0))
    occupancy2 = float(ex2.get("inbound_occupancy", 0))
    bo_hours = float(ex2.get("productive_hours_backoffice", 0))
    email_hours = float(ex2.get("productive_hours_email", 0))
    vacations = float(ex2.get("vacations", 0))
    aux_hours = float(ex2.get("auxiliary_hours", 0))

    answered2 = calls2 * nda2
    inbound_transactional_hours = answered2 * inbound_aht2 / 3600
    inbound_productive_hours = safe_div(inbound_transactional_hours, occupancy2)
    total_productive_hours = inbound_productive_hours + bo_hours + email_hours
    attended_hours = total_productive_hours + aux_hours
    scheduled_needed = safe_div(attended_hours, 1 - vacations)

    shift_rows = []
    total_answered = 0.0
    total_minutes = 0.0
    for shift in ex3.get("shifts", []):
        answered = float(shift.get("answered_calls", 0))
        minutes = float(shift.get("talk_minutes", 0)) + float(shift.get("acw_minutes", 0))
        aht = safe_div(minutes, answered) * 60
        row = dict(shift)
        row["aht_sec"] = aht
        shift_rows.append(row)
        total_answered += answered
        total_minutes += minutes

    return {
        "exercise1": {
            "attendance_hours": attendance_hours,
            "productive_hours": productive_hours,
            "occupancy": occ,
            "transactional_hours": transactional_hours,
            "answered_calls": answered_calls,
            "inbound_aht_sec": inbound_aht_sec,
        },
        "exercise2": {
            "answered_calls": answered2,
            "inbound_transactional_hours": inbound_transactional_hours,
            "inbound_productive_hours": inbound_productive_hours,
            "total_productive_hours": total_productive_hours,
            "attended_hours": attended_hours,
            "scheduled_hours": scheduled_needed,
        },
        "exercise3": {
            "shifts": shift_rows,
            "global_aht_sec": safe_div(total_minutes, total_answered) * 60,
            "recommendations": ex3.get("recommendations", []),
        },
    }


def calculate_dimensioning(payload: dict[str, Any]) -> dict[str, Any]:
    weekly_calls = float(payload.get("weekly_calls", 0))
    absenteeism = float(payload.get("absenteeism", 0))
    auxiliaries = float(payload.get("auxiliaries", 0))
    aht_sec = float(payload.get("aht_sec", 0))
    ft_hours_week = float(payload.get("ft_hours_week", 45))
    pt_hours_week = float(payload.get("pt_hours_week", 24))
    occupancy = float(payload.get("occupancy_target", 0.85))
    sla_time_sec = float(payload.get("sla_time_sec", 20))
    sla_level = float(payload.get("sla_level", 0.8))
    pt_ratio = float(payload.get("part_time_ratio", 0))

    shrinkage = safe_div(1, (1 - absenteeism) * (1 - auxiliaries))

    rows = []
    total_pct = total_calls = total_calls_hour = total_erlang = 0.0
    total_agents_position = total_hc_shrinkage = 0
    total_fte_day = 0.0

    for day in payload.get("days", []):
        traffic_pct = float(day.get("traffic_pct", 0))
        operating_hours = float(day.get("operating_hours", 0))
        calls_day = weekly_calls * traffic_pct
        calls_hour = safe_div(calls_day, operating_hours)
        erlang = calls_hour * aht_sec / 3600
        agents_position = round_up(safe_div(erlang, occupancy)) if operating_hours > 0 and occupancy else 0
        hc_shrinkage = round_up(agents_position * shrinkage) if agents_position else 0
        fte_day = safe_div(calls_day * aht_sec / 3600 / occupancy * shrinkage, operating_hours) if operating_hours > 0 and occupancy else 0
        agents_erlang = erlang_c_required_agents(erlang, aht_sec, sla_time_sec, sla_level) if operating_hours > 0 else 0
        service_level_erlang = erlang_c_service_level(erlang, agents_erlang, sla_time_sec, aht_sec) if agents_erlang else 0

        rows.append({
            "day": day.get("day", ""),
            "traffic_pct": traffic_pct,
            "calls_day": calls_day,
            "operating_hours": operating_hours,
            "calls_hour": calls_hour,
            "traffic_erlang": erlang,
            "agents_position": agents_position,
            "hc_shrinkage": hc_shrinkage,
            "fte_day": fte_day,
            "fte_week_accumulated": fte_day,
            "agents_erlang_c": agents_erlang,
            "service_level_erlang_c": service_level_erlang,
        })

        total_pct += traffic_pct
        total_calls += calls_day
        total_calls_hour += calls_hour
        total_erlang += erlang
        total_agents_position += agents_position
        total_hc_shrinkage += hc_shrinkage
        total_fte_day += fte_day

    hc_peak = max((row["hc_shrinkage"] for row in rows), default=0)
    solo_ft = {
        "hc_peak_required": hc_peak,
        "part_time_ratio": 0,
        "ft_people": hc_peak,
        "pt_people": 0,
        "total_people": hc_peak,
        "fte_from_ft": hc_peak,
        "fte_from_pt": 0,
        "fte_total": hc_peak,
    }

    ft_people = round_up(hc_peak * (1 - pt_ratio))
    pt_people = round_up(hc_peak * pt_ratio)
    fte_from_ft = safe_div(ft_people * ft_hours_week, ft_hours_week)
    fte_from_pt = safe_div(pt_people * pt_hours_week, ft_hours_week)
    mix_total_fte = fte_from_ft + fte_from_pt

    mix = {
        "hc_peak_required": hc_peak,
        "part_time_ratio": pt_ratio,
        "ft_people": ft_people,
        "pt_people": pt_people,
        "total_people": ft_people + pt_people,
        "fte_from_ft": fte_from_ft,
        "fte_from_pt": fte_from_pt,
        "fte_total": mix_total_fte,
    }

    return {
        "assumptions": {
            "weekly_calls": weekly_calls,
            "aht_sec": aht_sec,
            "absenteeism": absenteeism,
            "auxiliaries": auxiliaries,
            "shrinkage": shrinkage,
            "occupancy_target": occupancy,
            "sla_time_sec": sla_time_sec,
            "sla_level": sla_level,
            "ft_hours_week": ft_hours_week,
            "pt_hours_week": pt_hours_week,
        },
        "rows": rows,
        "totals": {
            "traffic_pct": total_pct,
            "calls_day": total_calls,
            "calls_hour": total_calls_hour,
            "traffic_erlang": total_erlang,
            "agents_position": total_agents_position,
            "hc_shrinkage": total_hc_shrinkage,
            "fte_day": total_fte_day,
            "fte_week_accumulated": total_fte_day,
        },
        "contract_model": {
            "solo_ft": solo_ft,
            "ft_pt_mix": mix,
            "fte_saving": solo_ft["fte_total"] - mix["fte_total"],
            "fte_saving_pct": safe_div(solo_ft["fte_total"] - mix["fte_total"], solo_ft["fte_total"]),
            "note": "El cálculo principal replica la lógica del Excel: tráfico Erlang / ocupación objetivo, más shrinkage. También se entrega la referencia Erlang C por día.",
        },
    }

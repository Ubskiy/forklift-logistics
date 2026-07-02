"""FastAPI backend для будущего iOS-приложения."""

from __future__ import annotations

from dataclasses import asdict
from typing import Literal, Optional

from fastapi import FastAPI
from pydantic import BaseModel, Field

from app.core import (
    build_simple_policy,
    evaluate_objective,
    format_interval,
    format_minutes_hms,
    load_scenario,
    optimize_with_sa,
    run_simulation,
)


app = FastAPI(
    title="Forklift Logistics API",
    description="API для симуляции внутризаводской логистики и сравнения стратегий.",
    version="0.1.0",
)


class InitialInventoryIn(BaseModel):
    tubes_at_c1: Optional[int] = None
    shields_waiting_c2: Optional[int] = None
    shields_waiting_c3: Optional[int] = None
    finished_waiting_c4: Optional[int] = None


class HandlingTimesIn(BaseModel):
    tube_load_min: Optional[float] = Field(default=None, ge=0)
    tube_unload_min: Optional[float] = Field(default=None, ge=0)
    shield_load_min: Optional[float] = Field(default=None, ge=0)
    shield_unload_min: Optional[float] = Field(default=None, ge=0)
    finished_load_min: Optional[float] = Field(default=None, ge=0)
    finished_unload_min: Optional[float] = Field(default=None, ge=0)


class TravelTimesIn(BaseModel):
    s_c1: Optional[float] = Field(default=None, ge=0)
    c1_c2: Optional[float] = Field(default=None, ge=0)
    c2_c3: Optional[float] = Field(default=None, ge=0)
    c3_c4: Optional[float] = Field(default=None, ge=0)
    c4_p: Optional[float] = Field(default=None, ge=0)


class ProductionRatesIn(BaseModel):
    c1_per_hour: Optional[float] = Field(default=None, ge=0)
    c2_per_hour: Optional[float] = Field(default=None, ge=0)
    c3_per_hour: Optional[float] = Field(default=None, ge=0)
    c4_per_hour: Optional[float] = Field(default=None, ge=0)


class ObjectiveWeightsIn(BaseModel):
    underproduction_penalty: Optional[float] = Field(default=None, ge=0)
    makespan_weight: Optional[float] = Field(default=None, ge=0)
    c3_starvation_weight: Optional[float] = Field(default=None, ge=0)
    forklift_idle_weight: Optional[float] = Field(default=None, ge=0)


class AnnealingIn(BaseModel):
    iterations: Optional[int] = Field(default=None, ge=1, le=5000)
    initial_temperature: Optional[float] = Field(default=None, gt=0)
    cooling_rate: Optional[float] = Field(default=None, gt=0, lt=1)
    min_temperature: Optional[float] = Field(default=None, gt=0)
    seed: Optional[int] = Field(default=None, ge=0)


class CompareRequest(BaseModel):
    scenario: Literal["sample_day", "sample_night"] = "sample_day"
    order_shields_qty: Optional[int] = Field(default=None, ge=1)
    shift_duration_hours: Optional[float] = Field(default=None, gt=0)
    initial_inventory: Optional[InitialInventoryIn] = None
    handling: Optional[HandlingTimesIn] = None
    travel_times: Optional[TravelTimesIn] = None
    production: Optional[ProductionRatesIn] = None
    objective: Optional[ObjectiveWeightsIn] = None
    annealing: Optional[AnnealingIn] = None


def _set_route_time(scenario, src: str, dst: str, value: Optional[float]) -> None:
    if value is None:
        return
    scenario.travel_time_overrides_min[(src, dst)] = float(value)
    scenario.travel_time_overrides_min[(dst, src)] = float(value)


def _apply_request_to_scenario(payload: CompareRequest):
    scenario = load_scenario(payload.scenario)

    if payload.order_shields_qty is not None:
        scenario.order_shields_qty = payload.order_shields_qty
    if payload.shift_duration_hours is not None:
        scenario.shift_duration_hours = payload.shift_duration_hours

    if payload.initial_inventory is not None:
        inv = payload.initial_inventory
        if inv.tubes_at_c1 is not None:
            scenario.initial_tubes_at_c1 = inv.tubes_at_c1
        if inv.shields_waiting_c2 is not None:
            scenario.initial_shields_waiting_c2 = inv.shields_waiting_c2
        if inv.shields_waiting_c3 is not None:
            scenario.initial_shields_waiting_c3 = inv.shields_waiting_c3
        if inv.finished_waiting_c4 is not None:
            scenario.initial_finished_waiting_c4 = inv.finished_waiting_c4

    if payload.handling is not None:
        for key, value in payload.handling:
            if value is not None:
                setattr(scenario.handling, key, float(value))

    if payload.travel_times is not None:
        t = payload.travel_times
        _set_route_time(scenario, "S", "C1", t.s_c1)
        _set_route_time(scenario, "C1", "C2", t.c1_c2)
        _set_route_time(scenario, "C2", "C3", t.c2_c3)
        _set_route_time(scenario, "C3", "C4", t.c3_c4)
        _set_route_time(scenario, "C4", "P", t.c4_p)

    if payload.production is not None:
        for key, value in payload.production:
            if value is not None:
                setattr(scenario.production, key, float(value))

    if payload.objective is not None:
        for key, value in payload.objective:
            if value is not None:
                setattr(scenario.objective, key, float(value))

    if payload.annealing is not None:
        for key, value in payload.annealing:
            if value is not None:
                setattr(scenario.sa, key, value)

    return scenario


def _metrics_json(result) -> dict:
    data = asdict(result.metrics)
    data["makespan_hms"] = format_minutes_hms(result.metrics.makespan_min)
    data["c3_starvation_hms"] = format_minutes_hms(result.metrics.c3_starvation_min)
    data["total_forklift_idle_hms"] = format_minutes_hms(result.metrics.total_forklift_idle_min)
    data["avoidable_forklift_idle_hms"] = format_minutes_hms(result.metrics.avoidable_forklift_idle_min)
    return data


def _trip_json(trip, shift_start: str) -> dict:
    data = asdict(trip)
    data["route"] = trip.route
    data["interval"] = format_interval(trip.start_time_min, trip.end_time_min, shift_start)
    data["load_interval"] = format_interval(trip.load_start_min, trip.load_end_min, shift_start)
    data["travel_interval"] = format_interval(trip.travel_start_min, trip.travel_end_min, shift_start)
    data["unload_interval"] = format_interval(trip.unload_start_min, trip.unload_end_min, shift_start)
    return data


def _result_json(result, shift_start: str) -> dict:
    return {
        "strategy_name": result.strategy_name,
        "metrics": _metrics_json(result),
        "objective_breakdown": result.meta.get("objective_breakdown", {}),
        "route_stats": [asdict(item) for item in result.route_stats],
        "trip_log": [_trip_json(item, shift_start) for item in result.trip_records],
        "meta": result.meta,
    }


def _scenario_json(scenario) -> dict:
    return {
        "name": scenario.name,
        "shift_type": scenario.shift_type,
        "shift_start_hhmm": scenario.shift_start_hhmm,
        "shift_duration_hours": scenario.shift_duration_hours,
        "order_shields_qty": scenario.order_shields_qty,
        "forklift": asdict(scenario.forklift),
        "handling": asdict(scenario.handling),
        "production": asdict(scenario.production),
        "objective": asdict(scenario.objective),
        "annealing": asdict(scenario.sa),
        "buffers": asdict(scenario.buffers),
        "initial_inventory": {
            "tubes_at_c1": scenario.initial_tubes_at_c1,
            "shields_waiting_c2": scenario.initial_shields_waiting_c2,
            "shields_waiting_c3": scenario.initial_shields_waiting_c3,
            "finished_waiting_c4": scenario.initial_finished_waiting_c4,
        },
    }


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "forklift-logistics-api"}


@app.get("/scenarios")
def scenarios() -> dict:
    return {
        "items": [
            {"id": "sample_day", "title": "Дневная смена"},
            {"id": "sample_night", "title": "Ночная смена"},
        ]
    }


@app.get("/scenarios/{name}")
def scenario_details(name: Literal["sample_day", "sample_night"]) -> dict:
    return _scenario_json(load_scenario(name))


@app.post("/compare")
def compare(payload: CompareRequest) -> dict:
    scenario = _apply_request_to_scenario(payload)

    greedy = run_simulation(
        scenario=scenario,
        strategy_name="simple",
        policy=build_simple_policy(),
    )
    evaluate_objective(greedy, scenario)

    seed = scenario.sa.seed if payload.annealing is None else payload.annealing.seed
    sa = optimize_with_sa(scenario, seed=seed).best_result
    evaluate_objective(sa, scenario)

    return {
        "scenario": _scenario_json(scenario),
        "greedy": _result_json(greedy, scenario.shift_start_hhmm),
        "simulated_annealing": _result_json(sa, scenario.shift_start_hhmm),
        "delta": {
            "shipped_qty": sa.metrics.shipped_qty - greedy.metrics.shipped_qty,
            "shortfall_qty": sa.metrics.shortfall_qty - greedy.metrics.shortfall_qty,
            "objective_value": sa.metrics.objective_value - greedy.metrics.objective_value,
            "c3_starvation_min": sa.metrics.c3_starvation_min - greedy.metrics.c3_starvation_min,
            "trips_total": sa.metrics.trips_total - greedy.metrics.trips_total,
        },
    }

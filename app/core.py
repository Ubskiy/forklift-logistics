"""Единый модуль проекта: сценарии, симуляция, оптимизация, отчёты, графики."""

from __future__ import annotations

from collections import defaultdict
import contextlib
from dataclasses import dataclass, field
import heapq
import io
import math
from math import floor
from pathlib import Path
import random
from typing import Any

# ==============================
# Константы сценариев
# ==============================

NODES: tuple[str, ...] = ("S", "C1", "C2", "C3", "C4", "P")
ROUTE_SEQUENCE: tuple[str, ...] = ("S->C1", "C1->C2", "C2->C3", "C3->C4", "C4->P")

ROUTE_TRAVEL_TIME_MIN: dict[tuple[str, str], float] = {
    ("S", "C1"): 6.0,
    ("C1", "C2"): 6.0,
    ("C2", "C3"): 6.0,
    ("C3", "C4"): 10.0,
    ("C4", "P"): 6.0,
}

# ==============================
# Доменные dataclass
# ==============================


@dataclass
class ForkliftConfig:
    count: int = 2
    speed_kmh: float = 15.0
    max_weight_kg: float = 1700.0
    max_shields_per_trip: int = 10
    max_tubes_per_trip: int = 14
    max_trips_per_hour: int = 4


@dataclass
class HandlingTimes:
    tube_load_min: float = 5.0
    tube_unload_min: float = 4.0
    shield_load_min: float = 5.0
    shield_unload_min: float = 4.0
    finished_load_min: float = 5.0
    finished_unload_min: float = 4.0


@dataclass
class ProductionRates:
    c1_per_hour: float
    c2_per_hour: float
    c3_per_hour: float
    c4_per_hour: float


@dataclass
class ObjectiveWeights:
    underproduction_penalty: float = 15000.0
    makespan_weight: float = 1.0
    c3_starvation_weight: float = 25.0
    forklift_idle_weight: float = 4.0
    wip_weight: float = 6.0
    route_fragmentation_weight: float = 2.0
    violation_penalty_weight: float = 100000.0


@dataclass
class SAConfig:
    iterations: int = 240
    initial_temperature: float = 90.0
    cooling_rate: float = 0.99
    min_temperature: float = 0.1
    seed: int = 42


@dataclass
class BatchSettings:
    tubes_per_trip_default: int = 10
    shields_per_trip_default: int = 6
    finished_per_trip_default: int = 6


@dataclass
class BufferSettings:
    c1_tube_input_capacity: int = 30
    c1_output_capacity: int = 16
    c2_input_capacity: int = 18
    c2_output_capacity: int = 16
    c3_input_capacity: int = 10
    c3_output_capacity: int = 8
    c4_input_capacity: int = 12
    c4_output_capacity: int = 10
    wip_target_units: int = 20


@dataclass
class PipeConsumption:
    pipes_6800_per_shield: float = 1.0
    pipes_6200_per_shield: float = 1.0

    @property
    def total_pipes_per_shield(self) -> float:
        return self.pipes_6800_per_shield + self.pipes_6200_per_shield


@dataclass
class Scenario:
    name: str
    shift_type: str
    shift_duration_hours: float
    shift_start_hhmm: str
    order_shields_qty: int
    forklift: ForkliftConfig
    handling: HandlingTimes
    production: ProductionRates
    objective: ObjectiveWeights = field(default_factory=ObjectiveWeights)
    sa: SAConfig = field(default_factory=SAConfig)
    batches: BatchSettings = field(default_factory=BatchSettings)
    buffers: BufferSettings = field(default_factory=BufferSettings)
    pipes: PipeConsumption = field(default_factory=PipeConsumption)
    tube_unit_weight_kg: float = 120.0
    shield_unit_weight_kg: float = 160.0
    initial_tubes_at_c1: int = 0
    initial_shields_waiting_c2: int = 0
    initial_shields_waiting_c3: int = 0
    initial_finished_waiting_c4: int = 0
    travel_time_overrides_min: dict[tuple[str, str], float] = field(default_factory=dict)
    max_overtime_min: float = 240.0
    random_seed: int = 42

    def shift_duration_min(self) -> float:
        return self.shift_duration_hours * 60.0

    def required_tubes_for_order(self) -> int:
        return math.ceil(self.order_shields_qty * self.pipes.total_pipes_per_shield)


@dataclass
class TripRecord:
    strategy_name: str
    forklift_id: str
    trip_id: int
    cargo_type: str
    route_from: str
    route_to: str
    qty: float
    unit_weight: float
    total_weight: float
    start_time_min: float
    load_start_min: float
    load_end_min: float
    travel_start_min: float
    travel_end_min: float
    unload_start_min: float
    unload_end_min: float
    end_time_min: float
    duration_minutes: float
    was_idle_before_trip: bool
    idle_before_trip_minutes: float

    @property
    def route(self) -> str:
        return f"{self.route_from}->{self.route_to}"


@dataclass
class RouteStats:
    route: str
    trips_count: int
    total_units: float
    shields_qty: float
    tubes_qty: float
    total_weight_kg: float
    total_duration_min: float
    avg_trip_size: float
    trips_share_pct: float
    volume_share_pct: float
    busy_time_min: float


@dataclass
class SimulationMetrics:
    makespan_min: float = 0.0
    total_forklift_idle_min: float = 0.0
    forklift_idle_by_id: dict[str, float] = field(default_factory=dict)
    c3_starvation_min: float = 0.0
    total_shop_starvation_min: float = 0.0
    shortfall_qty: float = 0.0
    violation_count: int = 0
    moved_tubes: float = 0.0
    moved_shields: float = 0.0
    shipped_qty: float = 0.0
    trips_total: int = 0
    avg_trip_load_units: float = 0.0
    avg_trip_load_factor: float = 0.0
    avg_forklift_utilization: float = 0.0
    excessive_wip_penalty: float = 0.0
    route_fragmentation_penalty: float = 0.0
    objective_value: float = 0.0


@dataclass
class SimulationResult:
    strategy_name: str
    metrics: SimulationMetrics
    trip_records: list[TripRecord] = field(default_factory=list)
    route_stats: list[RouteStats] = field(default_factory=list)
    meta: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class BatchOverride:
    tubes_per_trip: int
    shields_per_trip: int
    finished_per_trip: int


@dataclass(frozen=True)
class DispatchPolicy:
    route_order: tuple[str, ...]
    batch_override: BatchOverride | None = None


@dataclass(frozen=True)
class RouteSpec:
    route_id: str
    source_node: str
    destination_node: str
    source_key: str
    destination_key: str | None
    destination_capacity: float | None
    cargo_type: str
    unit_weight: float
    load_min: float
    unload_min: float
    travel_min: float
    max_qty_per_trip: int
    batch_qty: int


@dataclass(order=True)
class ArrivalEvent:
    at_min: float
    route_id: str = field(compare=False)
    qty: float = field(compare=False)


@dataclass
class ForkliftState:
    forklift_id: str
    free_at_min: float = 0.0
    busy_min: float = 0.0
    idle_min: float = 0.0
    trip_starts_min: list[float] = field(default_factory=list)


@dataclass
class PlantBuffers:
    source_tubes: float
    tubes_c1: float
    c1_out: float
    c2_in: float
    c2_out: float
    c3_in: float
    c3_out: float
    c4_in: float
    c4_out: float
    shipped: float


@dataclass
class SimState:
    last_update_min: float
    buffers: PlantBuffers
    reserved_inbound: dict[str, float]
    reserved_to_ship: float
    starvation_by_shop_min: dict[str, float]
    peak_wip_units: float
    violation_count: int
    arrivals: list[ArrivalEvent]


@dataclass
class ObjectiveBreakdown:
    shipped_qty: float
    underproduction_qty: float
    underproduction_component: float
    makespan_component: float
    c3_starvation_component: float
    forklift_idle_component: float
    wip_component: float
    fragmentation_component: float
    violation_component: float
    total: float


@dataclass(frozen=True)
class PolicyCandidate:
    route_order: tuple[str, ...]
    batch: BatchOverride


@dataclass
class SAIteration:
    iteration: int
    temperature: float
    current_objective: float
    best_objective: float


@dataclass
class SAResult:
    best_candidate: PolicyCandidate
    best_policy: DispatchPolicy
    best_result: SimulationResult
    best_objective: float
    iterations_done: int
    history: list[SAIteration] = field(default_factory=list)


# ==============================
# Сценарии
# ==============================


def _travel_bidirectional(base: dict[tuple[str, str], float]) -> dict[tuple[str, str], float]:
    out: dict[tuple[str, str], float] = {}
    for (a, b), v in base.items():
        out[(a, b)] = float(v)
        out.setdefault((b, a), float(v))
    return out


def build_default_day_scenario() -> Scenario:
    return Scenario(
        name="sample_day",
        shift_type="day",
        shift_duration_hours=11.0,
        shift_start_hhmm="08:00",
        order_shields_qty=88,
        forklift=ForkliftConfig(),
        handling=HandlingTimes(),
        production=ProductionRates(c1_per_hour=8.0, c2_per_hour=12.0, c3_per_hour=8.0, c4_per_hour=12.0),
        objective=ObjectiveWeights(),
        sa=SAConfig(),
        batches=BatchSettings(),
        buffers=BufferSettings(),
        pipes=PipeConsumption(),
        tube_unit_weight_kg=120.0,
        shield_unit_weight_kg=160.0,
        initial_tubes_at_c1=8,
        initial_shields_waiting_c2=2,
        initial_shields_waiting_c3=0,
        initial_finished_waiting_c4=0,
        travel_time_overrides_min=_travel_bidirectional(ROUTE_TRAVEL_TIME_MIN),
        max_overtime_min=240.0,
        random_seed=42,
    )


def build_default_night_scenario() -> Scenario:
    return Scenario(
        name="sample_night",
        shift_type="night",
        shift_duration_hours=11.0,
        shift_start_hhmm="20:00",
        order_shields_qty=44,
        forklift=ForkliftConfig(),
        handling=HandlingTimes(),
        production=ProductionRates(c1_per_hour=4.0, c2_per_hour=12.0, c3_per_hour=8.0, c4_per_hour=12.0),
        objective=ObjectiveWeights(),
        sa=SAConfig(),
        batches=BatchSettings(),
        buffers=BufferSettings(),
        pipes=PipeConsumption(),
        tube_unit_weight_kg=120.0,
        shield_unit_weight_kg=160.0,
        initial_tubes_at_c1=6,
        initial_shields_waiting_c2=1,
        initial_shields_waiting_c3=0,
        initial_finished_waiting_c4=0,
        travel_time_overrides_min=_travel_bidirectional(ROUTE_TRAVEL_TIME_MIN),
        max_overtime_min=240.0,
        random_seed=42,
    )


def load_scenario(name: str = "sample_day") -> Scenario:
    normalized = name.strip().lower()
    if normalized in {"sample_day", "day"}:
        return build_default_day_scenario()
    if normalized in {"sample_night", "night"}:
        return build_default_night_scenario()
    raise ValueError(f"Unknown scenario name: {name}")


# ==============================
# Симуляция
# ==============================


def build_simple_policy() -> DispatchPolicy:
    return DispatchPolicy(route_order=ROUTE_SEQUENCE)


def _travel_time_min(scenario: Scenario, src: str, dst: str) -> float:
    if (src, dst) in scenario.travel_time_overrides_min:
        return float(scenario.travel_time_overrides_min[(src, dst)])
    raise KeyError(f"Нет настроенного плеча: {src}->{dst}")


def _clamp_batches(scenario: Scenario, override: BatchOverride | None) -> BatchOverride:
    if override is None:
        return BatchOverride(
            tubes_per_trip=scenario.batches.tubes_per_trip_default,
            shields_per_trip=scenario.batches.shields_per_trip_default,
            finished_per_trip=scenario.batches.finished_per_trip_default,
        )

    tube_max_by_weight = int(floor(scenario.forklift.max_weight_kg / max(scenario.tube_unit_weight_kg, 1e-9)))
    shield_max_by_weight = int(floor(scenario.forklift.max_weight_kg / max(scenario.shield_unit_weight_kg, 1e-9)))

    return BatchOverride(
        tubes_per_trip=max(1, min(override.tubes_per_trip, scenario.forklift.max_tubes_per_trip, tube_max_by_weight)),
        shields_per_trip=max(1, min(override.shields_per_trip, scenario.forklift.max_shields_per_trip, shield_max_by_weight)),
        finished_per_trip=max(1, min(override.finished_per_trip, scenario.forklift.max_shields_per_trip, shield_max_by_weight)),
    )


def _build_route_specs(scenario: Scenario, batch: BatchOverride) -> dict[str, RouteSpec]:
    tube_max_by_weight = int(floor(scenario.forklift.max_weight_kg / max(scenario.tube_unit_weight_kg, 1e-9)))
    shield_max_by_weight = int(floor(scenario.forklift.max_weight_kg / max(scenario.shield_unit_weight_kg, 1e-9)))

    return {
        "S->C1": RouteSpec("S->C1", "S", "C1", "source_tubes", "tubes_c1", float(scenario.buffers.c1_tube_input_capacity), "трубы", scenario.tube_unit_weight_kg, scenario.handling.tube_load_min, scenario.handling.tube_unload_min, _travel_time_min(scenario, "S", "C1"), max(1, min(scenario.forklift.max_tubes_per_trip, tube_max_by_weight)), batch.tubes_per_trip),
        "C1->C2": RouteSpec("C1->C2", "C1", "C2", "c1_out", "c2_in", float(scenario.buffers.c2_input_capacity), "щиты", scenario.shield_unit_weight_kg, scenario.handling.shield_load_min, scenario.handling.shield_unload_min, _travel_time_min(scenario, "C1", "C2"), max(1, min(scenario.forklift.max_shields_per_trip, shield_max_by_weight)), batch.shields_per_trip),
        "C2->C3": RouteSpec("C2->C3", "C2", "C3", "c2_out", "c3_in", float(scenario.buffers.c3_input_capacity), "щиты", scenario.shield_unit_weight_kg, scenario.handling.shield_load_min, scenario.handling.shield_unload_min, _travel_time_min(scenario, "C2", "C3"), max(1, min(scenario.forklift.max_shields_per_trip, shield_max_by_weight)), batch.shields_per_trip),
        "C3->C4": RouteSpec("C3->C4", "C3", "C4", "c3_out", "c4_in", float(scenario.buffers.c4_input_capacity), "щиты", scenario.shield_unit_weight_kg, scenario.handling.shield_load_min, scenario.handling.shield_unload_min, _travel_time_min(scenario, "C3", "C4"), max(1, min(scenario.forklift.max_shields_per_trip, shield_max_by_weight)), batch.shields_per_trip),
        "C4->P": RouteSpec("C4->P", "C4", "P", "c4_out", None, None, "готовые щиты", scenario.shield_unit_weight_kg, scenario.handling.finished_load_min, scenario.handling.finished_unload_min, _travel_time_min(scenario, "C4", "P"), max(1, min(scenario.forklift.max_shields_per_trip, shield_max_by_weight)), batch.finished_per_trip),
    }


def _buffer_value(buffers: PlantBuffers, key: str) -> float:
    return float(getattr(buffers, key))


def _set_buffer_value(buffers: PlantBuffers, key: str, value: float) -> None:
    setattr(buffers, key, float(value))


def _calc_wip(buffers: PlantBuffers) -> float:
    return max(0.0, buffers.c1_out + buffers.c2_in + buffers.c2_out + buffers.c3_in + buffers.c3_out + buffers.c4_in + buffers.c4_out)


def _produce_for_interval(state: SimState, scenario: Scenario, dt_min: float) -> None:
    if dt_min <= 0.0:
        return

    b = state.buffers
    rates = scenario.production
    buf = scenario.buffers
    pipes_per_shield = max(scenario.pipes.total_pipes_per_shield, 1e-9)

    c1_rate, c2_rate, c3_rate, c4_rate = rates.c1_per_hour / 60.0, rates.c2_per_hour / 60.0, rates.c3_per_hour / 60.0, rates.c4_per_hour / 60.0

    if b.tubes_c1 <= 1e-9:
        state.starvation_by_shop_min["C1"] += dt_min
    c1_actual = min(c1_rate * dt_min, b.tubes_c1 / pipes_per_shield, max(0.0, buf.c1_output_capacity - b.c1_out))
    b.tubes_c1 -= c1_actual * pipes_per_shield
    b.c1_out += c1_actual

    if b.c2_in <= 1e-9:
        state.starvation_by_shop_min["C2"] += dt_min
    c2_actual = min(c2_rate * dt_min, b.c2_in, max(0.0, buf.c2_output_capacity - b.c2_out))
    b.c2_in -= c2_actual
    b.c2_out += c2_actual

    if b.c3_in <= 1e-9:
        state.starvation_by_shop_min["C3"] += dt_min
    c3_actual = min(c3_rate * dt_min, b.c3_in, max(0.0, buf.c3_output_capacity - b.c3_out))
    b.c3_in -= c3_actual
    b.c3_out += c3_actual

    if b.c4_in <= 1e-9:
        state.starvation_by_shop_min["C4"] += dt_min
    c4_actual = min(c4_rate * dt_min, b.c4_in, max(0.0, buf.c4_output_capacity - b.c4_out))
    b.c4_in -= c4_actual
    b.c4_out += c4_actual

    state.peak_wip_units = max(state.peak_wip_units, _calc_wip(b))


def _apply_arrival(state: SimState, scenario: Scenario, route_specs: dict[str, RouteSpec], event: ArrivalEvent) -> None:
    spec = route_specs[event.route_id]
    b = state.buffers

    if spec.destination_key is None:
        b.shipped += event.qty
        state.reserved_to_ship = max(0.0, state.reserved_to_ship - event.qty)
        return

    cap_map = {
        "tubes_c1": float(scenario.buffers.c1_tube_input_capacity),
        "c2_in": float(scenario.buffers.c2_input_capacity),
        "c3_in": float(scenario.buffers.c3_input_capacity),
        "c4_in": float(scenario.buffers.c4_input_capacity),
    }
    cap = cap_map.get(spec.destination_key, float("inf"))

    before = _buffer_value(b, spec.destination_key)
    after = before + event.qty
    if after > cap + 1e-9:
        state.violation_count += 1
        after = cap

    _set_buffer_value(b, spec.destination_key, after)
    state.reserved_inbound[spec.destination_key] = max(0.0, state.reserved_inbound.get(spec.destination_key, 0.0) - event.qty)


def _advance_state_to(state: SimState, scenario: Scenario, route_specs: dict[str, RouteSpec], target_time_min: float) -> None:
    target = max(target_time_min, state.last_update_min)

    while state.last_update_min + 1e-9 < target:
        next_time = target
        if state.arrivals and state.arrivals[0].at_min < next_time:
            next_time = state.arrivals[0].at_min

        _produce_for_interval(state, scenario, max(0.0, next_time - state.last_update_min))
        state.last_update_min = next_time

        while state.arrivals and state.arrivals[0].at_min <= state.last_update_min + 1e-9:
            _apply_arrival(state, scenario, route_specs, heapq.heappop(state.arrivals))


def _enforce_trip_limit(forklift: ForkliftState, candidate_start_min: float, max_trips_per_hour: int) -> float:
    start = candidate_start_min
    while True:
        recent = [t for t in forklift.trip_starts_min if start - t < 60.0]
        if len(recent) < max_trips_per_hour:
            return start
        start = min(recent) + 60.0


def _remaining_final_demand(scenario: Scenario, state: SimState) -> float:
    return max(0.0, float(scenario.order_shields_qty) - state.buffers.shipped - state.reserved_to_ship)


def _select_feasible_trip(scenario: Scenario, state: SimState, route_specs: dict[str, RouteSpec], route_order: tuple[str, ...]) -> tuple[RouteSpec, int] | None:
    b = state.buffers
    pipes_per_shield = max(scenario.pipes.total_pipes_per_shield, 1e-9)

    for route_id in route_order:
        spec = route_specs[route_id]
        source_available = _buffer_value(b, spec.source_key)
        if source_available < 1.0:
            continue

        if spec.destination_key is None:
            dest_free = float("inf")
        else:
            reserved = state.reserved_inbound.get(spec.destination_key, 0.0)
            now = _buffer_value(b, spec.destination_key)
            dest_free = (spec.destination_capacity if spec.destination_capacity is not None else float("inf")) - now - reserved
            if dest_free < 1.0:
                continue

        qty_max = min(source_available, dest_free, float(spec.max_qty_per_trip), float(spec.batch_qty))

        if route_id == "C4->P":
            qty_max = min(qty_max, _remaining_final_demand(scenario, state))

        if route_id == "S->C1":
            remaining_shields = max(0.0, float(scenario.order_shields_qty) - b.shipped)
            remaining_tube_need = max(0.0, remaining_shields * pipes_per_shield - b.tubes_c1)
            soft_cap = min(float(scenario.buffers.c1_tube_input_capacity), remaining_tube_need + spec.batch_qty)
            qty_max = min(qty_max, soft_cap - b.tubes_c1 - state.reserved_inbound.get("tubes_c1", 0.0))

        qty = int(floor(qty_max))
        if qty >= 1:
            return spec, qty

    return None


def _next_event_time(state: SimState, scenario: Scenario, current_time_min: float) -> float | None:
    b, rates, buf = state.buffers, scenario.production, scenario.buffers
    candidates: list[float] = []

    if state.arrivals and state.arrivals[0].at_min > current_time_min + 1e-9:
        candidates.append(state.arrivals[0].at_min)

    c1_rate, c2_rate, c3_rate, c4_rate = rates.c1_per_hour / 60.0, rates.c2_per_hour / 60.0, rates.c3_per_hour / 60.0, rates.c4_per_hour / 60.0

    if b.c1_out < 1.0 and b.tubes_c1 > 0.0 and b.c1_out < buf.c1_output_capacity - 1e-9 and c1_rate > 1e-9:
        candidates.append(current_time_min + max(0.0, (1.0 - b.c1_out) / c1_rate))
    if b.c2_out < 1.0 and b.c2_in > 0.0 and b.c2_out < buf.c2_output_capacity - 1e-9 and c2_rate > 1e-9:
        candidates.append(current_time_min + max(0.0, (1.0 - b.c2_out) / c2_rate))
    if b.c3_out < 1.0 and b.c3_in > 0.0 and b.c3_out < buf.c3_output_capacity - 1e-9 and c3_rate > 1e-9:
        candidates.append(current_time_min + max(0.0, (1.0 - b.c3_out) / c3_rate))
    if b.c4_out < 1.0 and b.c4_in > 0.0 and b.c4_out < buf.c4_output_capacity - 1e-9 and c4_rate > 1e-9:
        candidates.append(current_time_min + max(0.0, (1.0 - b.c4_out) / c4_rate))

    return min(candidates) if candidates else None


def _dispatch_trip(*, scenario: Scenario, state: SimState, forklift: ForkliftState, spec: RouteSpec, qty: int, start_time_min: float, trip_id: int, strategy_name: str) -> TripRecord:
    idle_before = max(0.0, start_time_min - forklift.free_at_min)
    if idle_before > 0.0:
        forklift.idle_min += idle_before

    load_start = start_time_min
    load_end = load_start + spec.load_min
    travel_start = load_end
    travel_end = travel_start + spec.travel_min
    unload_start = travel_end
    unload_end = unload_start + spec.unload_min
    end_time = unload_end

    _set_buffer_value(state.buffers, spec.source_key, max(0.0, _buffer_value(state.buffers, spec.source_key) - float(qty)))

    if spec.destination_key is None:
        state.reserved_to_ship += float(qty)
    else:
        state.reserved_inbound[spec.destination_key] = state.reserved_inbound.get(spec.destination_key, 0.0) + float(qty)

    heapq.heappush(state.arrivals, ArrivalEvent(at_min=unload_end, route_id=spec.route_id, qty=float(qty)))

    duration = end_time - start_time_min
    forklift.busy_min += duration
    forklift.free_at_min = end_time
    forklift.trip_starts_min.append(start_time_min)

    return TripRecord(
        strategy_name=strategy_name,
        forklift_id=forklift.forklift_id,
        trip_id=trip_id,
        cargo_type=spec.cargo_type,
        route_from=spec.source_node,
        route_to=spec.destination_node,
        qty=float(qty),
        unit_weight=spec.unit_weight,
        total_weight=float(qty) * spec.unit_weight,
        start_time_min=start_time_min,
        load_start_min=load_start,
        load_end_min=load_end,
        travel_start_min=travel_start,
        travel_end_min=travel_end,
        unload_start_min=unload_start,
        unload_end_min=unload_end,
        end_time_min=end_time,
        duration_minutes=duration,
        was_idle_before_trip=idle_before > 1e-9,
        idle_before_trip_minutes=idle_before,
    )


def _build_route_stats(trips: list[TripRecord]) -> list[RouteStats]:
    agg: dict[str, dict[str, float]] = {
        route: {"trips_count": 0.0, "total_units": 0.0, "shields_qty": 0.0, "tubes_qty": 0.0, "total_weight_kg": 0.0, "total_duration_min": 0.0}
        for route in ROUTE_SEQUENCE
    }

    total_trips = len(trips)
    total_units = sum(item.qty for item in trips)

    for item in trips:
        a = agg[item.route]
        a["trips_count"] += 1.0
        a["total_units"] += item.qty
        if item.cargo_type == "трубы":
            a["tubes_qty"] += item.qty
        else:
            a["shields_qty"] += item.qty
        a["total_weight_kg"] += item.total_weight
        a["total_duration_min"] += item.duration_minutes

    out: list[RouteStats] = []
    for route in ROUTE_SEQUENCE:
        values = agg[route]
        trips_count = int(values["trips_count"])
        total_route_units = values["total_units"]
        out.append(RouteStats(route, trips_count, total_route_units, values["shields_qty"], values["tubes_qty"], values["total_weight_kg"], values["total_duration_min"], total_route_units / max(trips_count, 1), 100.0 * trips_count / max(total_trips, 1), 100.0 * total_route_units / max(total_units, 1e-9), values["total_duration_min"]))
    return out


def _avg_load_factor(trips: list[TripRecord], route_specs: dict[str, RouteSpec]) -> float:
    if not trips:
        return 0.0
    factors = [min(1.0, trip.qty / max(float(route_specs[trip.route].max_qty_per_trip), 1e-9)) for trip in trips]
    return sum(factors) / len(factors) if factors else 0.0


def _route_fragmentation_metric(trips: list[TripRecord], route_specs: dict[str, RouteSpec]) -> float:
    if not trips:
        return 0.0
    empty = [1.0 - min(1.0, trip.qty / max(float(route_specs[trip.route].max_qty_per_trip), 1e-9)) for trip in trips]
    return 100.0 * sum(empty) / len(empty) if empty else 0.0


def run_simulation(scenario: Scenario, *, strategy_name: str, policy: DispatchPolicy) -> SimulationResult:
    batch = _clamp_batches(scenario, policy.batch_override)
    route_specs = _build_route_specs(scenario, batch)

    state = SimState(
        last_update_min=0.0,
        buffers=PlantBuffers(
            source_tubes=float(max(0, scenario.required_tubes_for_order() * 2)),
            tubes_c1=float(scenario.initial_tubes_at_c1),
            c1_out=0.0,
            c2_in=0.0,
            c2_out=float(scenario.initial_shields_waiting_c2),
            c3_in=0.0,
            c3_out=float(scenario.initial_shields_waiting_c3),
            c4_in=0.0,
            c4_out=float(scenario.initial_finished_waiting_c4),
            shipped=0.0,
        ),
        reserved_inbound={"tubes_c1": 0.0, "c2_in": 0.0, "c3_in": 0.0, "c4_in": 0.0},
        reserved_to_ship=0.0,
        starvation_by_shop_min={"C1": 0.0, "C2": 0.0, "C3": 0.0, "C4": 0.0},
        peak_wip_units=0.0,
        violation_count=0,
        arrivals=[],
    )

    forklifts = [ForkliftState(forklift_id=f"FL-{idx + 1}") for idx in range(scenario.forklift.count)]
    trips: list[TripRecord] = []

    horizon_min = scenario.shift_duration_min() + scenario.max_overtime_min
    trip_id = 0

    for _ in range(50000):
        if state.buffers.shipped >= float(scenario.order_shields_qty) - 1e-9:
            break

        forklifts.sort(key=lambda item: (item.free_at_min, item.forklift_id))
        forklift = forklifts[0]
        if forklift.free_at_min > horizon_min + 1e-9:
            break

        _advance_state_to(state, scenario, route_specs, forklift.free_at_min)

        prev_free = forklift.free_at_min
        start = min(_enforce_trip_limit(forklift, prev_free, scenario.forklift.max_trips_per_hour), horizon_min)
        if start > prev_free + 1e-9:
            _advance_state_to(state, scenario, route_specs, start)

        selected = _select_feasible_trip(scenario, state, route_specs, policy.route_order)

        if selected is None:
            nxt = _next_event_time(state, scenario, start)
            if nxt is None:
                break
            nxt = min(horizon_min, max(nxt, start))
            if nxt <= prev_free + 1e-9:
                nxt = min(horizon_min, prev_free + 1.0)
            forklift.idle_min += max(0.0, nxt - prev_free)
            forklift.free_at_min = nxt
            continue

        spec, qty = selected
        if start > horizon_min + 1e-9:
            break

        trip_id += 1
        trips.append(_dispatch_trip(scenario=scenario, state=state, forklift=forklift, spec=spec, qty=qty, start_time_min=start, trip_id=trip_id, strategy_name=strategy_name))

    makespan_min = max([trip.end_time_min for trip in trips], default=0.0)
    if makespan_min > 0.0:
        _advance_state_to(state, scenario, route_specs, makespan_min)

    for forklift in forklifts:
        if makespan_min > forklift.free_at_min:
            forklift.idle_min += makespan_min - forklift.free_at_min

    metrics = SimulationMetrics(
        makespan_min=makespan_min,
        total_forklift_idle_min=sum(item.idle_min for item in forklifts),
        forklift_idle_by_id={item.forklift_id: item.idle_min for item in forklifts},
        c3_starvation_min=state.starvation_by_shop_min.get("C3", 0.0),
        total_shop_starvation_min=sum(state.starvation_by_shop_min.values()),
        shortfall_qty=max(0.0, float(scenario.order_shields_qty) - state.buffers.shipped),
        violation_count=state.violation_count,
        moved_tubes=sum(item.qty for item in trips if item.route == "S->C1"),
        moved_shields=sum(item.qty for item in trips if item.route == "C4->P"),
        shipped_qty=state.buffers.shipped,
        trips_total=len(trips),
        avg_trip_load_units=(sum(item.qty for item in trips) / max(len(trips), 1)),
        avg_trip_load_factor=_avg_load_factor(trips, route_specs),
        avg_forklift_utilization=(0.0 if makespan_min <= 1e-9 else sum(item.busy_min / makespan_min for item in forklifts) / max(len(forklifts), 1)),
        excessive_wip_penalty=max(0.0, state.peak_wip_units - float(scenario.buffers.wip_target_units)),
        route_fragmentation_penalty=_route_fragmentation_metric(trips, route_specs),
    )

    return SimulationResult(
        strategy_name=strategy_name,
        metrics=metrics,
        trip_records=sorted(trips, key=lambda x: (x.start_time_min, x.forklift_id, x.trip_id)),
        route_stats=_build_route_stats(trips),
        meta={
            "batch_config": {"tubes_per_trip": batch.tubes_per_trip, "shields_per_trip": batch.shields_per_trip, "finished_per_trip": batch.finished_per_trip},
            "route_order": list(policy.route_order),
            "starvation_by_shop_min": dict(state.starvation_by_shop_min),
            "forklift_busy_by_id": {item.forklift_id: item.busy_min for item in forklifts},
            "forklift_idle_by_id": {item.forklift_id: item.idle_min for item in forklifts},
            "peak_wip_units": state.peak_wip_units,
        },
    )


# ==============================
# Objective + SA
# ==============================


def evaluate_objective(result: SimulationResult, scenario: Scenario) -> ObjectiveBreakdown:
    m = result.metrics
    w = scenario.objective

    underproduction = max(0.0, float(scenario.order_shields_qty) - m.shipped_qty)

    under_component = w.underproduction_penalty * underproduction
    makespan_component = w.makespan_weight * m.makespan_min
    c3_component = w.c3_starvation_weight * m.c3_starvation_min
    idle_component = w.forklift_idle_weight * m.total_forklift_idle_min
    wip_component = w.wip_weight * m.excessive_wip_penalty
    fragmentation_component = w.route_fragmentation_weight * m.route_fragmentation_penalty
    violation_component = w.violation_penalty_weight * float(m.violation_count)

    total = under_component + makespan_component + c3_component + idle_component + wip_component + fragmentation_component + violation_component
    m.objective_value = total
    m.shortfall_qty = underproduction

    breakdown = ObjectiveBreakdown(
        shipped_qty=m.shipped_qty,
        underproduction_qty=underproduction,
        underproduction_component=under_component,
        makespan_component=makespan_component,
        c3_starvation_component=c3_component,
        forklift_idle_component=idle_component,
        wip_component=wip_component,
        fragmentation_component=fragmentation_component,
        violation_component=violation_component,
        total=total,
    )
    result.meta["objective_breakdown"] = breakdown.__dict__
    return breakdown


def _as_policy(candidate: PolicyCandidate) -> DispatchPolicy:
    return DispatchPolicy(route_order=candidate.route_order, batch_override=candidate.batch)


def _mutate_route_order(order: tuple[str, ...], rng: random.Random) -> tuple[str, ...]:
    seq = list(order)
    if rng.random() < 0.55:
        i, j = sorted(rng.sample(range(len(seq)), 2))
        seq[i], seq[j] = seq[j], seq[i]
        return tuple(seq)
    i, j = rng.randrange(len(seq)), rng.randrange(len(seq))
    item = seq.pop(i)
    seq.insert(j, item)
    return tuple(seq)


def _clamp_batch_for_sa(scenario: Scenario, batch: BatchOverride) -> BatchOverride:
    tube_max, shield_max = scenario.forklift.max_tubes_per_trip, scenario.forklift.max_shields_per_trip
    return BatchOverride(max(1, min(tube_max, batch.tubes_per_trip)), max(1, min(shield_max, batch.shields_per_trip)), max(1, min(shield_max, batch.finished_per_trip)))


def _mutate_batch(candidate: PolicyCandidate, scenario: Scenario, rng: random.Random) -> BatchOverride:
    name, step = rng.choice(["tubes", "shields", "finished"]), rng.choice([-1, 1])
    b = candidate.batch
    if name == "tubes":
        b = BatchOverride(b.tubes_per_trip + step, b.shields_per_trip, b.finished_per_trip)
    elif name == "shields":
        b = BatchOverride(b.tubes_per_trip, b.shields_per_trip + step, b.finished_per_trip)
    else:
        b = BatchOverride(b.tubes_per_trip, b.shields_per_trip, b.finished_per_trip + step)
    return _clamp_batch_for_sa(scenario, b)


def _mutate(candidate: PolicyCandidate, scenario: Scenario, rng: random.Random) -> PolicyCandidate:
    if rng.random() < 0.6:
        return PolicyCandidate(route_order=_mutate_route_order(candidate.route_order, rng), batch=candidate.batch)
    return PolicyCandidate(route_order=candidate.route_order, batch=_mutate_batch(candidate, scenario, rng))


def optimize_with_sa(scenario: Scenario, seed: int | None = None) -> SAResult:
    rng = random.Random(scenario.random_seed if seed is None else seed)

    current = PolicyCandidate(
        route_order=("C4->P", "C3->C4", "C2->C3", "C1->C2", "S->C1"),
        batch=BatchOverride(scenario.batches.tubes_per_trip_default, scenario.batches.shields_per_trip_default, scenario.batches.finished_per_trip_default),
    )

    current_policy = _as_policy(current)
    current_result = run_simulation(scenario=scenario, strategy_name="simulated_annealing", policy=current_policy)
    current_obj = evaluate_objective(current_result, scenario).total

    best, best_policy, best_result, best_obj = current, current_policy, current_result, current_obj
    temperature = scenario.sa.initial_temperature
    history: list[SAIteration] = []
    iterations_done = 0

    for i in range(scenario.sa.iterations):
        iterations_done = i + 1
        if temperature < scenario.sa.min_temperature:
            break

        neighbor = _mutate(current, scenario, rng)
        neighbor_policy = _as_policy(neighbor)
        neighbor_result = run_simulation(scenario=scenario, strategy_name="simulated_annealing", policy=neighbor_policy)
        neighbor_obj = evaluate_objective(neighbor_result, scenario).total

        delta = neighbor_obj - current_obj
        accept = delta <= 0 or (rng.random() < math.exp(-delta / max(temperature, 1e-9)))

        if accept:
            current, current_policy, current_result, current_obj = neighbor, neighbor_policy, neighbor_result, neighbor_obj

        if current_obj < best_obj:
            best, best_policy, best_result, best_obj = current, current_policy, current_result, current_obj

        history.append(SAIteration(iteration=i, temperature=temperature, current_objective=current_obj, best_objective=best_obj))
        temperature *= scenario.sa.cooling_rate

    return SAResult(best_candidate=best, best_policy=best_policy, best_result=best_result, best_objective=best_obj, iterations_done=iterations_done, history=history)


# ==============================
# Форматирование вывода
# ==============================


def format_minutes_hms(minutes: float) -> str:
    total_seconds = max(0, int(round(minutes * 60.0)))
    hours, rem = divmod(total_seconds, 3600)
    mins, secs = divmod(rem, 60)
    return f"{hours:02d}:{mins:02d}:{secs:02d}"


def _parse_hhmm(value: str) -> int:
    hh, mm = value.split(":", maxsplit=1)
    return int(hh) * 60 + int(mm)


def format_clock_time(offset_minutes: float, shift_start_hhmm: str) -> str:
    start_min = _parse_hhmm(shift_start_hhmm)
    absolute = int(round(offset_minutes + start_min))
    hh = (absolute // 60) % 24
    mm = absolute % 60
    return f"{hh:02d}:{mm:02d}"


def format_interval(start_min: float, end_min: float, shift_start_hhmm: str) -> str:
    return f"{format_clock_time(start_min, shift_start_hhmm)}-{format_clock_time(end_min, shift_start_hhmm)}"


def route_stats_table(result: SimulationResult) -> str:
    lines = [
        "Маршрут | Рейсов | Щитов | Труб | Вес, кг | Время, мин | Ср. партия | % рейсов | % объёма",
        "-----------------------------------------------------------------------------------------",
    ]
    for row in result.route_stats:
        lines.append(
            f"{row.route:7s} | {row.trips_count:6d} | {row.shields_qty:5.1f} | {row.tubes_qty:4.1f} | {row.total_weight_kg:7.0f} | {row.total_duration_min:10.1f} | {row.avg_trip_size:10.2f} | {row.trips_share_pct:7.2f}% | {row.volume_share_pct:7.2f}%"
        )
    return "\n".join(lines)


def trip_log_table(result: SimulationResult, shift_start_hhmm: str) -> str:
    if not result.trip_records:
        return "(рейсов нет)"

    lines: list[str] = []
    for trip in result.trip_records:
        lines.append(
            f"{format_interval(trip.start_time_min, trip.end_time_min, shift_start_hhmm)} | {trip.forklift_id:4s} | {trip.route:7s} | {trip.cargo_type:13s} | qty={trip.qty:4.0f} | {trip.total_weight:6.0f} кг | погр:{format_interval(trip.load_start_min, trip.load_end_min, shift_start_hhmm)} | путь:{format_interval(trip.travel_start_min, trip.travel_end_min, shift_start_hhmm)} | выгр:{format_interval(trip.unload_start_min, trip.unload_end_min, shift_start_hhmm)} | idle_before={trip.idle_before_trip_minutes:5.1f} мин"
        )
    return "\n".join(lines)


def delta_table(base: SimulationResult, alt: SimulationResult) -> str:
    def m(r: SimulationResult) -> dict[str, float]:
        x = r.metrics
        return {
            "objective": x.objective_value,
            "makespan_min": x.makespan_min,
            "shipped_qty": x.shipped_qty,
            "shortfall_qty": x.shortfall_qty,
            "c3_starvation_min": x.c3_starvation_min,
            "forklift_idle_min": x.total_forklift_idle_min,
            "trips_total": float(x.trips_total),
            "avg_trip_qty": x.avg_trip_load_units,
            "avg_trip_load_factor_pct": 100.0 * x.avg_trip_load_factor,
            "avg_forklift_utilization_pct": 100.0 * x.avg_forklift_utilization,
        }

    b, a = m(base), m(alt)
    rows = [
        ("Отгружено щитов", "shipped_qty"),
        ("Недовыпуск", "shortfall_qty"),
        ("Общее время, мин", "makespan_min"),
        ("Простой C3, мин", "c3_starvation_min"),
        ("Простой погрузчиков, мин", "forklift_idle_min"),
        ("Число рейсов", "trips_total"),
        ("Средняя партия", "avg_trip_qty"),
        ("Средняя загрузка рейса, %", "avg_trip_load_factor_pct"),
        ("Средняя загрузка погрузчиков, %", "avg_forklift_utilization_pct"),
        ("Целевая функция", "objective"),
    ]
    lines = ["Показатель | Простая | Отжиг | Разница (Отжиг-Простая)", "---------------------------------------------------------"]
    for title, key in rows:
        lines.append(f"{title:30s} | {b[key]:8.2f} | {a[key]:8.2f} | {a[key] - b[key]:10.2f}")
    return "\n".join(lines)


def ascii_timeline(result: SimulationResult, shift_start_hhmm: str, width: int = 80) -> str:
    if not result.trip_records:
        return "(рейсов нет)"

    makespan = max(item.end_time_min for item in result.trip_records)
    buckets = max(20, width)
    per_forklift: dict[str, list[str]] = defaultdict(lambda: ["." for _ in range(buckets)])

    route_char = {"S->C1": "S", "C1->C2": "1", "C2->C3": "2", "C3->C4": "3", "C4->P": "P"}

    for trip in result.trip_records:
        start_idx = int((trip.start_time_min / makespan) * (buckets - 1))
        end_idx = int((trip.end_time_min / makespan) * (buckets - 1))
        for idx in range(max(0, start_idx), min(buckets, end_idx + 1)):
            per_forklift[trip.forklift_id][idx] = route_char.get(trip.route, "#")

    lines = [f"Таймлайн {shift_start_hhmm} -> {format_clock_time(makespan, shift_start_hhmm)}", "Легенда: S=S->C1, 1=C1->C2, 2=C2->C3, 3=C3->C4, P=C4->P, .=простой"]
    for forklift_id in sorted(per_forklift):
        lines.append(f"{forklift_id:4s} | {''.join(per_forklift[forklift_id])}")
    return "\n".join(lines)


# ==============================
# Matplotlib таймлайн
# ==============================


def _matplotlib():
    stderr_buffer = io.StringIO()
    stdout_buffer = io.StringIO()
    with contextlib.redirect_stderr(stderr_buffer), contextlib.redirect_stdout(stdout_buffer):
        try:
            import matplotlib.pyplot as plt  # type: ignore
        except Exception:
            raise RuntimeError("Matplotlib недоступен в этом окружении. Установите/переустановите matplotlib в venv.") from None
    return plt


def save_forklift_timeline_plot(result: SimulationResult, output_path: str | Path, *, shift_start_hhmm: str, title: str | None = None) -> Path:
    plt = _matplotlib()

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)

    trips = result.trip_records
    if not trips:
        fig, ax = plt.subplots(figsize=(10, 3))
        ax.set_title(title or f"{result.strategy_name}: таймлайн")
        ax.text(0.5, 0.5, "Рейсы отсутствуют", ha="center", va="center", transform=ax.transAxes)
        ax.axis("off")
        fig.tight_layout()
        fig.savefig(output, dpi=140)
        plt.close(fig)
        return output

    route_color = {
        "S->C1": "#4C78A8",
        "C1->C2": "#F58518",
        "C2->C3": "#54A24B",
        "C3->C4": "#E45756",
        "C4->P": "#72B7B2",
    }

    forklifts = sorted({item.forklift_id for item in trips})
    y_map = {forklift_id: idx for idx, forklift_id in enumerate(forklifts)}
    max_time = max(item.end_time_min for item in trips)

    fig, ax = plt.subplots(figsize=(14, max(3.4, 1.1 * len(forklifts) + 1.8)))

    for trip in trips:
        y = y_map[trip.forklift_id]
        color = route_color.get(trip.route, "#777777")
        ax.broken_barh([(trip.start_time_min, trip.duration_minutes)], (y - 0.275, 0.55), facecolors=color, alpha=0.9)
        if trip.duration_minutes >= 7.0:
            ax.text(trip.start_time_min + trip.duration_minutes / 2, y, trip.route, color="white", ha="center", va="center", fontsize=8, fontweight="bold")

    tick_step = 60 if max_time > 180 else 30
    xticks = list(range(0, int(max_time) + tick_step, tick_step))
    ax.set_xticks(xticks)
    ax.set_xticklabels([format_clock_time(float(t), shift_start_hhmm) for t in xticks])
    ax.set_yticks(list(y_map.values()))
    ax.set_yticklabels(forklifts)
    ax.set_xlabel("Время")
    ax.set_ylabel("Погрузчик")
    ax.set_xlim(0, max(1.0, max_time))
    ax.grid(axis="x", alpha=0.25)

    handles = [plt.Line2D([0], [0], color=route_color[r], lw=8, label=r) for r in ROUTE_SEQUENCE]
    ax.legend(handles=handles, title="Маршрут", ncol=5, frameon=False, loc="upper center", bbox_to_anchor=(0.5, 1.16))

    ax.set_title(title or f"{result.strategy_name}: таймлайн погрузчиков")
    fig.tight_layout()
    fig.savefig(output, dpi=150)
    plt.close(fig)
    return output

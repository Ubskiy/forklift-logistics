"""Событийная симуляция внутризаводской логистики с явным таймлайном рейсов."""

from __future__ import annotations

from dataclasses import dataclass, field
import heapq
from math import floor
from typing import Any

from app.domain.entities import RouteStats, SimulationMetrics, SimulationResult, TripRecord
from app.domain.scenario import Scenario

ROUTE_SEQUENCE: tuple[str, ...] = ("S->C1", "C1->C2", "C2->C3", "C3->C4", "C4->P")


@dataclass(frozen=True)
class BatchOverride:
    tubes_per_trip: int
    shields_per_trip: int
    finished_per_trip: int


@dataclass(frozen=True)
class DispatchPolicy:
    """Правило диспетчеризации: порядок маршрутов и размеры партий."""

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


def _travel_time_min(scenario: Scenario, src: str, dst: str) -> float:
    if (src, dst) in scenario.travel_time_overrides_min:
        return float(scenario.travel_time_overrides_min[(src, dst)])

    if (src, dst) in scenario.travel_distances_m:
        distance = scenario.travel_distances_m[(src, dst)]
        speed_m_per_min = scenario.forklift.speed_kmh * 1000.0 / 60.0
        return float(distance / max(speed_m_per_min, 1e-9))

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
        tubes_per_trip=max(
            1,
            min(
                override.tubes_per_trip,
                scenario.forklift.max_tubes_per_trip,
                tube_max_by_weight,
            ),
        ),
        shields_per_trip=max(
            1,
            min(
                override.shields_per_trip,
                scenario.forklift.max_shields_per_trip,
                shield_max_by_weight,
            ),
        ),
        finished_per_trip=max(
            1,
            min(
                override.finished_per_trip,
                scenario.forklift.max_shields_per_trip,
                shield_max_by_weight,
            ),
        ),
    )


def _build_route_specs(scenario: Scenario, batch: BatchOverride) -> dict[str, RouteSpec]:
    tube_max_by_weight = int(floor(scenario.forklift.max_weight_kg / max(scenario.tube_unit_weight_kg, 1e-9)))
    shield_max_by_weight = int(floor(scenario.forklift.max_weight_kg / max(scenario.shield_unit_weight_kg, 1e-9)))

    return {
        "S->C1": RouteSpec(
            route_id="S->C1",
            source_node="S",
            destination_node="C1",
            source_key="source_tubes",
            destination_key="tubes_c1",
            destination_capacity=float(scenario.buffers.c1_tube_input_capacity),
            cargo_type="трубы",
            unit_weight=scenario.tube_unit_weight_kg,
            load_min=scenario.handling.tube_load_min,
            unload_min=scenario.handling.tube_unload_min,
            travel_min=_travel_time_min(scenario, "S", "C1"),
            max_qty_per_trip=max(1, min(scenario.forklift.max_tubes_per_trip, tube_max_by_weight)),
            batch_qty=batch.tubes_per_trip,
        ),
        "C1->C2": RouteSpec(
            route_id="C1->C2",
            source_node="C1",
            destination_node="C2",
            source_key="c1_out",
            destination_key="c2_in",
            destination_capacity=float(scenario.buffers.c2_input_capacity),
            cargo_type="щиты",
            unit_weight=scenario.shield_unit_weight_kg,
            load_min=scenario.handling.shield_load_min,
            unload_min=scenario.handling.shield_unload_min,
            travel_min=_travel_time_min(scenario, "C1", "C2"),
            max_qty_per_trip=max(1, min(scenario.forklift.max_shields_per_trip, shield_max_by_weight)),
            batch_qty=batch.shields_per_trip,
        ),
        "C2->C3": RouteSpec(
            route_id="C2->C3",
            source_node="C2",
            destination_node="C3",
            source_key="c2_out",
            destination_key="c3_in",
            destination_capacity=float(scenario.buffers.c3_input_capacity),
            cargo_type="щиты",
            unit_weight=scenario.shield_unit_weight_kg,
            load_min=scenario.handling.shield_load_min,
            unload_min=scenario.handling.shield_unload_min,
            travel_min=_travel_time_min(scenario, "C2", "C3"),
            max_qty_per_trip=max(1, min(scenario.forklift.max_shields_per_trip, shield_max_by_weight)),
            batch_qty=batch.shields_per_trip,
        ),
        "C3->C4": RouteSpec(
            route_id="C3->C4",
            source_node="C3",
            destination_node="C4",
            source_key="c3_out",
            destination_key="c4_in",
            destination_capacity=float(scenario.buffers.c4_input_capacity),
            cargo_type="щиты",
            unit_weight=scenario.shield_unit_weight_kg,
            load_min=scenario.handling.shield_load_min,
            unload_min=scenario.handling.shield_unload_min,
            travel_min=_travel_time_min(scenario, "C3", "C4"),
            max_qty_per_trip=max(1, min(scenario.forklift.max_shields_per_trip, shield_max_by_weight)),
            batch_qty=batch.shields_per_trip,
        ),
        "C4->P": RouteSpec(
            route_id="C4->P",
            source_node="C4",
            destination_node="P",
            source_key="c4_out",
            destination_key=None,
            destination_capacity=None,
            cargo_type="готовые щиты",
            unit_weight=scenario.shield_unit_weight_kg,
            load_min=scenario.handling.finished_load_min,
            unload_min=scenario.handling.finished_unload_min,
            travel_min=_travel_time_min(scenario, "C4", "P"),
            max_qty_per_trip=max(1, min(scenario.forklift.max_shields_per_trip, shield_max_by_weight)),
            batch_qty=batch.finished_per_trip,
        ),
    }


def _buffer_value(buffers: PlantBuffers, key: str) -> float:
    return float(getattr(buffers, key))


def _set_buffer_value(buffers: PlantBuffers, key: str, value: float) -> None:
    setattr(buffers, key, float(value))


def _calc_wip(buffers: PlantBuffers) -> float:
    return max(
        0.0,
        buffers.c1_out + buffers.c2_in + buffers.c2_out + buffers.c3_in + buffers.c3_out + buffers.c4_in + buffers.c4_out,
    )


def _produce_for_interval(state: SimState, scenario: Scenario, dt_min: float) -> None:
    if dt_min <= 0.0:
        return

    b = state.buffers
    rates = scenario.production
    buf = scenario.buffers
    pipes_per_shield = max(scenario.pipes.total_pipes_per_shield, 1e-9)

    c1_rate = rates.c1_per_hour / 60.0
    c2_rate = rates.c2_per_hour / 60.0
    c3_rate = rates.c3_per_hour / 60.0
    c4_rate = rates.c4_per_hour / 60.0

    # C1: трубы -> щиты
    if b.tubes_c1 <= 1e-9:
        state.starvation_by_shop_min["C1"] += dt_min
    c1_possible = c1_rate * dt_min
    c1_cap_space = max(0.0, buf.c1_output_capacity - b.c1_out)
    c1_actual = min(c1_possible, b.tubes_c1 / pipes_per_shield, c1_cap_space)
    b.tubes_c1 -= c1_actual * pipes_per_shield
    b.c1_out += c1_actual

    # C2
    if b.c2_in <= 1e-9:
        state.starvation_by_shop_min["C2"] += dt_min
    c2_possible = c2_rate * dt_min
    c2_cap_space = max(0.0, buf.c2_output_capacity - b.c2_out)
    c2_actual = min(c2_possible, b.c2_in, c2_cap_space)
    b.c2_in -= c2_actual
    b.c2_out += c2_actual

    # C3 (узкое место)
    if b.c3_in <= 1e-9:
        state.starvation_by_shop_min["C3"] += dt_min
    c3_possible = c3_rate * dt_min
    c3_cap_space = max(0.0, buf.c3_output_capacity - b.c3_out)
    c3_actual = min(c3_possible, b.c3_in, c3_cap_space)
    b.c3_in -= c3_actual
    b.c3_out += c3_actual

    # C4
    if b.c4_in <= 1e-9:
        state.starvation_by_shop_min["C4"] += dt_min
    c4_possible = c4_rate * dt_min
    c4_cap_space = max(0.0, buf.c4_output_capacity - b.c4_out)
    c4_actual = min(c4_possible, b.c4_in, c4_cap_space)
    b.c4_in -= c4_actual
    b.c4_out += c4_actual

    state.peak_wip_units = max(state.peak_wip_units, _calc_wip(b))


def _apply_arrival(state: SimState, scenario: Scenario, route_specs: dict[str, RouteSpec], event: ArrivalEvent) -> None:
    spec = route_specs[event.route_id]
    b = state.buffers

    if spec.destination_key is None:
        # C4 -> P
        b.shipped += event.qty
        state.reserved_to_ship = max(0.0, state.reserved_to_ship - event.qty)
        return

    if spec.destination_key == "tubes_c1":
        cap = float(scenario.buffers.c1_tube_input_capacity)
    elif spec.destination_key == "c2_in":
        cap = float(scenario.buffers.c2_input_capacity)
    elif spec.destination_key == "c3_in":
        cap = float(scenario.buffers.c3_input_capacity)
    elif spec.destination_key == "c4_in":
        cap = float(scenario.buffers.c4_input_capacity)
    else:
        cap = float("inf")

    before = _buffer_value(b, spec.destination_key)
    after = before + event.qty
    if after > cap + 1e-9:
        state.violation_count += 1
        after = cap

    _set_buffer_value(b, spec.destination_key, after)
    state.reserved_inbound[spec.destination_key] = max(0.0, state.reserved_inbound.get(spec.destination_key, 0.0) - event.qty)


def _advance_state_to(
    state: SimState,
    scenario: Scenario,
    route_specs: dict[str, RouteSpec],
    target_time_min: float,
) -> None:
    target = max(target_time_min, state.last_update_min)

    while state.last_update_min + 1e-9 < target:
        next_time = target
        if state.arrivals and state.arrivals[0].at_min < next_time:
            next_time = state.arrivals[0].at_min

        dt = max(0.0, next_time - state.last_update_min)
        _produce_for_interval(state, scenario, dt)
        state.last_update_min = next_time

        while state.arrivals and state.arrivals[0].at_min <= state.last_update_min + 1e-9:
            event = heapq.heappop(state.arrivals)
            _apply_arrival(state, scenario, route_specs, event)


def _enforce_trip_limit(forklift: ForkliftState, candidate_start_min: float, max_trips_per_hour: int) -> float:
    start = candidate_start_min
    while True:
        recent = [t for t in forklift.trip_starts_min if start - t < 60.0]
        if len(recent) < max_trips_per_hour:
            return start
        start = min(recent) + 60.0


def _remaining_final_demand(scenario: Scenario, state: SimState) -> float:
    return max(0.0, float(scenario.order_shields_qty) - state.buffers.shipped - state.reserved_to_ship)


def _select_feasible_trip(
    scenario: Scenario,
    state: SimState,
    route_specs: dict[str, RouteSpec],
    route_order: tuple[str, ...],
) -> tuple[RouteSpec, int] | None:
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
            if spec.destination_capacity is None:
                dest_free = float("inf")
            else:
                now = _buffer_value(b, spec.destination_key)
                dest_free = spec.destination_capacity - now - reserved
            if dest_free < 1.0:
                continue

        qty_max = min(source_available, dest_free, float(spec.max_qty_per_trip), float(spec.batch_qty))

        if route_id == "C4->P":
            qty_max = min(qty_max, _remaining_final_demand(scenario, state))

        if route_id == "S->C1":
            # Не перегружаем C1 трубами сверх разумной потребности.
            remaining_shields = max(0.0, float(scenario.order_shields_qty) - b.shipped)
            remaining_tube_need = max(0.0, remaining_shields * pipes_per_shield - b.tubes_c1)
            soft_cap = min(float(scenario.buffers.c1_tube_input_capacity), remaining_tube_need + spec.batch_qty)
            tube_free = soft_cap - b.tubes_c1 - state.reserved_inbound.get("tubes_c1", 0.0)
            qty_max = min(qty_max, tube_free)

        qty = int(floor(qty_max))
        if qty >= 1:
            return spec, qty

    return None


def _next_event_time(state: SimState, scenario: Scenario, current_time_min: float) -> float | None:
    b = state.buffers
    rates = scenario.production
    buf = scenario.buffers

    candidates: list[float] = []

    if state.arrivals and state.arrivals[0].at_min > current_time_min + 1e-9:
        candidates.append(state.arrivals[0].at_min)

    c1_rate = rates.c1_per_hour / 60.0
    c2_rate = rates.c2_per_hour / 60.0
    c3_rate = rates.c3_per_hour / 60.0
    c4_rate = rates.c4_per_hour / 60.0

    if b.c1_out < 1.0 and b.tubes_c1 > 0.0 and b.c1_out < buf.c1_output_capacity - 1e-9 and c1_rate > 1e-9:
        candidates.append(current_time_min + max(0.0, (1.0 - b.c1_out) / c1_rate))
    if b.c2_out < 1.0 and b.c2_in > 0.0 and b.c2_out < buf.c2_output_capacity - 1e-9 and c2_rate > 1e-9:
        candidates.append(current_time_min + max(0.0, (1.0 - b.c2_out) / c2_rate))
    if b.c3_out < 1.0 and b.c3_in > 0.0 and b.c3_out < buf.c3_output_capacity - 1e-9 and c3_rate > 1e-9:
        candidates.append(current_time_min + max(0.0, (1.0 - b.c3_out) / c3_rate))
    if b.c4_out < 1.0 and b.c4_in > 0.0 and b.c4_out < buf.c4_output_capacity - 1e-9 and c4_rate > 1e-9:
        candidates.append(current_time_min + max(0.0, (1.0 - b.c4_out) / c4_rate))

    if not candidates:
        return None
    return min(candidates)


def _consume_source(state: SimState, spec: RouteSpec, qty: float) -> None:
    before = _buffer_value(state.buffers, spec.source_key)
    after = max(0.0, before - qty)
    _set_buffer_value(state.buffers, spec.source_key, after)


def _dispatch_trip(
    *,
    scenario: Scenario,
    state: SimState,
    forklift: ForkliftState,
    spec: RouteSpec,
    qty: int,
    start_time_min: float,
    trip_id: int,
    strategy_name: str,
) -> TripRecord:
    prev_free = forklift.free_at_min
    idle_before = max(0.0, start_time_min - prev_free)

    if idle_before > 0.0:
        forklift.idle_min += idle_before

    load_start = start_time_min
    load_end = load_start + spec.load_min
    travel_start = load_end
    travel_end = travel_start + spec.travel_min
    unload_start = travel_end
    unload_end = unload_start + spec.unload_min
    end_time = unload_end

    _consume_source(state, spec, float(qty))

    if spec.destination_key is None:
        state.reserved_to_ship += float(qty)
    else:
        state.reserved_inbound[spec.destination_key] = state.reserved_inbound.get(spec.destination_key, 0.0) + float(qty)

    heapq.heappush(state.arrivals, ArrivalEvent(at_min=unload_end, route_id=spec.route_id, qty=float(qty)))

    duration = end_time - start_time_min
    forklift.busy_min += duration
    forklift.free_at_min = end_time
    forklift.trip_starts_min.append(start_time_min)

    record = TripRecord(
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
    return record


def _build_route_stats(trips: list[TripRecord]) -> list[RouteStats]:
    agg: dict[str, dict[str, float]] = {
        route: {
            "trips_count": 0.0,
            "total_units": 0.0,
            "shields_qty": 0.0,
            "tubes_qty": 0.0,
            "total_weight_kg": 0.0,
            "total_duration_min": 0.0,
        }
        for route in ROUTE_SEQUENCE
    }

    if not trips:
        return [
            RouteStats(
                route=route,
                trips_count=0,
                total_units=0.0,
                shields_qty=0.0,
                tubes_qty=0.0,
                total_weight_kg=0.0,
                total_duration_min=0.0,
                avg_trip_size=0.0,
                trips_share_pct=0.0,
                volume_share_pct=0.0,
                busy_time_min=0.0,
            )
            for route in ROUTE_SEQUENCE
        ]

    total_trips = len(trips)
    total_units = sum(item.qty for item in trips)

    for item in trips:
        route = item.route
        a = agg[route]
        a["trips_count"] += 1.0
        a["total_units"] += item.qty
        if item.cargo_type == "трубы":
            a["tubes_qty"] += item.qty
        else:
            a["shields_qty"] += item.qty
        a["total_weight_kg"] += item.total_weight
        a["total_duration_min"] += item.duration_minutes

    stats: list[RouteStats] = []
    for route in ROUTE_SEQUENCE:
        values = agg[route]
        trips_count = int(values["trips_count"])
        total_route_units = values["total_units"]
        stats.append(
            RouteStats(
                route=route,
                trips_count=trips_count,
                total_units=total_route_units,
                shields_qty=values["shields_qty"],
                tubes_qty=values["tubes_qty"],
                total_weight_kg=values["total_weight_kg"],
                total_duration_min=values["total_duration_min"],
                avg_trip_size=(total_route_units / max(trips_count, 1)),
                trips_share_pct=100.0 * trips_count / max(total_trips, 1),
                volume_share_pct=100.0 * total_route_units / max(total_units, 1e-9),
                busy_time_min=values["total_duration_min"],
            )
        )

    return stats


def _avg_load_factor(trips: list[TripRecord], route_specs: dict[str, RouteSpec]) -> float:
    if not trips:
        return 0.0

    factors: list[float] = []
    for trip in trips:
        spec = route_specs.get(trip.route)
        if spec is None:
            continue
        factors.append(min(1.0, trip.qty / max(float(spec.max_qty_per_trip), 1e-9)))

    if not factors:
        return 0.0
    return sum(factors) / len(factors)


def _route_fragmentation_metric(trips: list[TripRecord], route_specs: dict[str, RouteSpec]) -> float:
    if not trips:
        return 0.0

    empty_ratios: list[float] = []
    for trip in trips:
        spec = route_specs.get(trip.route)
        if spec is None:
            continue
        load_factor = min(1.0, trip.qty / max(float(spec.max_qty_per_trip), 1e-9))
        empty_ratios.append(1.0 - load_factor)

    if not empty_ratios:
        return 0.0

    return 100.0 * sum(empty_ratios) / len(empty_ratios)


def _default_source_tubes(scenario: Scenario) -> float:
    # В demo-модели подаём не бесконечный источник, а разумный запас.
    return float(max(0, scenario.required_tubes_for_order() * 2))


def run_simulation(
    scenario: Scenario,
    *,
    strategy_name: str,
    policy: DispatchPolicy,
) -> SimulationResult:
    """Прогоняет событийную симуляцию для одной стратегии."""

    batch = _clamp_batches(scenario, policy.batch_override)
    route_specs = _build_route_specs(scenario, batch)

    state = SimState(
        last_update_min=0.0,
        buffers=PlantBuffers(
            source_tubes=_default_source_tubes(scenario),
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
    max_iterations = 50000
    trip_id = 0

    for _ in range(max_iterations):
        if state.buffers.shipped >= float(scenario.order_shields_qty) - 1e-9:
            break

        forklifts.sort(key=lambda item: (item.free_at_min, item.forklift_id))
        forklift = forklifts[0]

        if forklift.free_at_min > horizon_min + 1e-9:
            break

        _advance_state_to(state, scenario, route_specs, forklift.free_at_min)

        prev_free = forklift.free_at_min
        earliest_start = _enforce_trip_limit(forklift, prev_free, scenario.forklift.max_trips_per_hour)
        earliest_start = min(earliest_start, horizon_min)

        if earliest_start > prev_free + 1e-9:
            _advance_state_to(state, scenario, route_specs, earliest_start)

        selected = _select_feasible_trip(scenario, state, route_specs, policy.route_order)

        if selected is None:
            next_time = _next_event_time(state, scenario, earliest_start)
            if next_time is None:
                # Нет будущих событий и нечего везти.
                break

            next_time = min(horizon_min, max(next_time, earliest_start))
            if next_time <= prev_free + 1e-9:
                next_time = min(horizon_min, prev_free + 1.0)

            forklift.idle_min += max(0.0, next_time - prev_free)
            forklift.free_at_min = next_time
            continue

        spec, qty = selected
        start_time = earliest_start

        if start_time > horizon_min + 1e-9:
            break

        trip_id += 1
        trip = _dispatch_trip(
            scenario=scenario,
            state=state,
            forklift=forklift,
            spec=spec,
            qty=qty,
            start_time_min=start_time,
            trip_id=trip_id,
            strategy_name=strategy_name,
        )
        trips.append(trip)

    makespan_min = max([trip.end_time_min for trip in trips], default=0.0)
    if makespan_min > 0.0:
        _advance_state_to(state, scenario, route_specs, makespan_min)

    for forklift in forklifts:
        if makespan_min > forklift.free_at_min:
            forklift.idle_min += makespan_min - forklift.free_at_min

    route_stats = _build_route_stats(trips)
    avg_load_factor = _avg_load_factor(trips, route_specs)

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
        avg_trip_load_factor=avg_load_factor,
        avg_forklift_utilization=(
            0.0
            if makespan_min <= 1e-9
            else sum(item.busy_min / makespan_min for item in forklifts) / max(len(forklifts), 1)
        ),
        excessive_wip_penalty=max(0.0, state.peak_wip_units - float(scenario.buffers.wip_target_units)),
        route_fragmentation_penalty=_route_fragmentation_metric(trips, route_specs),
    )

    meta: dict[str, Any] = {
        "batch_config": {
            "tubes_per_trip": batch.tubes_per_trip,
            "shields_per_trip": batch.shields_per_trip,
            "finished_per_trip": batch.finished_per_trip,
        },
        "route_order": list(policy.route_order),
        "starvation_by_shop_min": dict(state.starvation_by_shop_min),
        "forklift_busy_by_id": {item.forklift_id: item.busy_min for item in forklifts},
        "forklift_idle_by_id": {item.forklift_id: item.idle_min for item in forklifts},
        "peak_wip_units": state.peak_wip_units,
    }

    return SimulationResult(
        strategy_name=strategy_name,
        metrics=metrics,
        trip_records=sorted(trips, key=lambda item: (item.start_time_min, item.forklift_id, item.trip_id)),
        route_stats=route_stats,
        meta=meta,
    )


def run_static_simulation(scenario: Scenario, batch_override: BatchOverride | None = None) -> SimulationResult:
    """Совместимость со старым именем функции."""

    policy = DispatchPolicy(route_order=ROUTE_SEQUENCE, batch_override=batch_override)
    return run_simulation(scenario=scenario, strategy_name="simple", policy=policy)

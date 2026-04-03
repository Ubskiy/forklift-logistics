"""Сборка dataclass-конфигов из единого набора констант."""

from __future__ import annotations

from app.config import constants as c
from app.domain.enums import ShiftType
from app.domain.scenario import (
    BatchSettings,
    BufferSettings,
    ForkliftConfig,
    HandlingTimes,
    ObjectiveWeights,
    PipeConsumption,
    ProductionRates,
    SAConfig,
    Scenario,
    build_time_overrides,
    build_travel_distances,
)

DEFAULT_NODES: tuple[str, ...] = c.NODES

DEFAULT_TRAVEL_DISTANCES_M = build_travel_distances(c.ROUTE_DISTANCES_M)
DEFAULT_TRAVEL_TIME_OVERRIDES_MIN = build_time_overrides(c.ROUTE_TRAVEL_TIME_MIN)

DEFAULT_FORKLIFT = ForkliftConfig(
    count=c.FORKLIFT_COUNT,
    speed_kmh=c.FORKLIFT_SPEED_KMH,
    max_weight_kg=c.FORKLIFT_MAX_WEIGHT_KG,
    max_shields_per_trip=c.FORKLIFT_MAX_SHIELDS_PER_TRIP,
    max_tubes_per_trip=c.FORKLIFT_MAX_TUBES_PER_TRIP,
    max_trips_per_hour=c.FORKLIFT_MAX_TRIPS_PER_HOUR,
)

DEFAULT_HANDLING = HandlingTimes(
    tube_load_min=c.TUBE_LOAD_MIN,
    tube_unload_min=c.TUBE_UNLOAD_MIN,
    shield_load_min=c.SHIELD_LOAD_MIN,
    shield_unload_min=c.SHIELD_UNLOAD_MIN,
    finished_load_min=c.FINISHED_LOAD_MIN,
    finished_unload_min=c.FINISHED_UNLOAD_MIN,
)

DEFAULT_OBJECTIVE_WEIGHTS = ObjectiveWeights(
    underproduction_penalty=c.UNDERPRODUCTION_PENALTY,
    makespan_weight=c.W_MAKESPAN,
    c3_starvation_weight=c.W_C3_STARVATION,
    forklift_idle_weight=c.W_FORKLIFT_IDLE,
    wip_weight=c.W_WIP,
    route_fragmentation_weight=c.W_ROUTE_FRAGMENTATION,
    violation_penalty_weight=c.W_VIOLATION,
)

DEFAULT_PIPE_CONSUMPTION = PipeConsumption(
    pipes_6800_per_shield=c.PIPES_6800_PER_SHIELD,
    pipes_6200_per_shield=c.PIPES_6200_PER_SHIELD,
)

DEFAULT_SA = SAConfig(
    iterations=c.SA_ITERATIONS,
    initial_temperature=c.SA_INITIAL_TEMPERATURE,
    cooling_rate=c.SA_COOLING_RATE,
    min_temperature=c.SA_MIN_TEMPERATURE,
    seed=c.SA_SEED,
)

DEFAULT_BATCHES = BatchSettings(
    tubes_per_trip_default=c.TUBES_PER_TRIP_DEFAULT,
    shields_per_trip_default=c.SHIELDS_PER_TRIP_DEFAULT,
    finished_per_trip_default=c.FINISHED_PER_TRIP_DEFAULT,
)

DEFAULT_BUFFERS = BufferSettings(
    c1_tube_input_capacity=c.C1_TUBE_INPUT_CAPACITY,
    c1_output_capacity=c.C1_OUTPUT_CAPACITY,
    c2_input_capacity=c.C2_INPUT_CAPACITY,
    c2_output_capacity=c.C2_OUTPUT_CAPACITY,
    c3_input_capacity=c.C3_INPUT_CAPACITY,
    c3_output_capacity=c.C3_OUTPUT_CAPACITY,
    c4_input_capacity=c.C4_INPUT_CAPACITY,
    c4_output_capacity=c.C4_OUTPUT_CAPACITY,
    wip_target_units=c.WIP_TARGET_UNITS,
)


def build_default_day_scenario() -> Scenario:
    return Scenario(
        name="sample_day",
        shift_type=ShiftType.DAY,
        shift_duration_hours=c.DAY_SHIFT_HOURS,
        shift_start_hhmm=c.DAY_SHIFT_START_HHMM,
        order_shields_qty=c.DAY_ORDER_SHIELDS,
        forklift=DEFAULT_FORKLIFT,
        handling=DEFAULT_HANDLING,
        production=ProductionRates(
            c1_per_hour=c.C1_DAY_PER_HOUR,
            c2_per_hour=c.C2_PER_HOUR,
            c3_per_hour=c.C3_PER_HOUR,
            c4_per_hour=c.C4_PER_HOUR,
        ),
        objective=DEFAULT_OBJECTIVE_WEIGHTS,
        sa=DEFAULT_SA,
        batches=DEFAULT_BATCHES,
        buffers=DEFAULT_BUFFERS,
        pipes=DEFAULT_PIPE_CONSUMPTION,
        tube_unit_weight_kg=c.TUBE_UNIT_WEIGHT_KG,
        shield_unit_weight_kg=c.SHIELD_UNIT_WEIGHT_KG,
        travel_distances_m=dict(DEFAULT_TRAVEL_DISTANCES_M),
        travel_time_overrides_min=dict(DEFAULT_TRAVEL_TIME_OVERRIDES_MIN),
        initial_tubes_at_c1=c.DAY_INITIAL_TUBES_C1,
        initial_shields_waiting_c2=c.DAY_INITIAL_WAITING_C2,
        initial_shields_waiting_c3=c.DAY_INITIAL_WAITING_C3,
        initial_finished_waiting_c4=c.DAY_INITIAL_WAITING_C4,
        max_overtime_min=c.MAX_OVERTIME_MIN,
        random_seed=c.DEFAULT_RANDOM_SEED,
    )


def build_default_night_scenario() -> Scenario:
    return Scenario(
        name="sample_night",
        shift_type=ShiftType.NIGHT,
        shift_duration_hours=c.NIGHT_SHIFT_HOURS,
        shift_start_hhmm=c.NIGHT_SHIFT_START_HHMM,
        order_shields_qty=c.NIGHT_ORDER_SHIELDS,
        forklift=DEFAULT_FORKLIFT,
        handling=DEFAULT_HANDLING,
        production=ProductionRates(
            c1_per_hour=c.C1_NIGHT_PER_HOUR,
            c2_per_hour=c.C2_PER_HOUR,
            c3_per_hour=c.C3_PER_HOUR,
            c4_per_hour=c.C4_PER_HOUR,
        ),
        objective=DEFAULT_OBJECTIVE_WEIGHTS,
        sa=DEFAULT_SA,
        batches=DEFAULT_BATCHES,
        buffers=DEFAULT_BUFFERS,
        pipes=DEFAULT_PIPE_CONSUMPTION,
        tube_unit_weight_kg=c.TUBE_UNIT_WEIGHT_KG,
        shield_unit_weight_kg=c.SHIELD_UNIT_WEIGHT_KG,
        travel_distances_m=dict(DEFAULT_TRAVEL_DISTANCES_M),
        travel_time_overrides_min=dict(DEFAULT_TRAVEL_TIME_OVERRIDES_MIN),
        initial_tubes_at_c1=c.NIGHT_INITIAL_TUBES_C1,
        initial_shields_waiting_c2=c.NIGHT_INITIAL_WAITING_C2,
        initial_shields_waiting_c3=c.NIGHT_INITIAL_WAITING_C3,
        initial_finished_waiting_c4=c.NIGHT_INITIAL_WAITING_C4,
        max_overtime_min=c.MAX_OVERTIME_MIN,
        random_seed=c.DEFAULT_RANDOM_SEED,
    )

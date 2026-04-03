from __future__ import annotations

from app.config.defaults import build_default_day_scenario
from app.optimization.baseline_policies import build_simple_policy
from app.simulation.simulator import run_simulation


def test_trip_limit_per_hour_respected() -> None:
    scenario = build_default_day_scenario()
    result = run_simulation(scenario=scenario, strategy_name="simple", policy=build_simple_policy())

    starts_by_forklift: dict[str, list[float]] = {}
    for trip in result.trip_records:
        starts_by_forklift.setdefault(trip.forklift_id, []).append(trip.start_time_min)

    for starts in starts_by_forklift.values():
        starts.sort()
        for i, t in enumerate(starts):
            recent = [x for x in starts[: i + 1] if t - x < 60.0]
            assert len(recent) <= scenario.forklift.max_trips_per_hour


def test_cargo_limits_are_respected() -> None:
    scenario = build_default_day_scenario()
    result = run_simulation(scenario=scenario, strategy_name="simple", policy=build_simple_policy())

    for trip in result.trip_records:
        assert trip.total_weight <= scenario.forklift.max_weight_kg + 1e-9
        if trip.cargo_type == "трубы":
            assert trip.qty <= scenario.forklift.max_tubes_per_trip
        else:
            assert trip.qty <= scenario.forklift.max_shields_per_trip

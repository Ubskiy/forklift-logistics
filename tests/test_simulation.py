from __future__ import annotations

from app.config.defaults import build_default_day_scenario
from app.optimization.baseline_policies import build_simple_policy
from app.simulation.simulator import run_simulation


def test_trip_intervals_are_consistent() -> None:
    scenario = build_default_day_scenario()
    result = run_simulation(scenario=scenario, strategy_name="simple", policy=build_simple_policy())

    assert result.trip_records, "Должен быть хотя бы один рейс"

    for trip in result.trip_records:
        assert trip.start_time_min <= trip.load_start_min <= trip.load_end_min
        assert trip.load_end_min <= trip.travel_start_min <= trip.travel_end_min
        assert trip.travel_end_min <= trip.unload_start_min <= trip.unload_end_min
        assert trip.unload_end_min <= trip.end_time_min
        assert trip.duration_minutes > 0


def test_route_stats_exist_and_non_negative() -> None:
    scenario = build_default_day_scenario()
    result = run_simulation(scenario=scenario, strategy_name="simple", policy=build_simple_policy())

    assert result.route_stats
    for row in result.route_stats:
        assert row.trips_count >= 0
        assert row.total_units >= 0.0
        assert row.total_duration_min >= 0.0

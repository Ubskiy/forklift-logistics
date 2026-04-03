from __future__ import annotations

from app.config.defaults import build_default_day_scenario
from app.optimization.baseline_policies import build_simple_policy
from app.simulation.metrics import delta_table, format_clock_time, format_minutes_hms
from app.simulation.simulator import run_simulation


def test_format_time_helpers() -> None:
    assert format_minutes_hms(0.0) == "00:00:00"
    assert format_minutes_hms(1.5) == "00:01:30"
    assert format_clock_time(0.0, "08:00") == "08:00"
    assert format_clock_time(125.0, "08:00") == "10:05"


def test_delta_table_contains_main_metrics() -> None:
    scenario = build_default_day_scenario()
    base = run_simulation(scenario=scenario, strategy_name="simple", policy=build_simple_policy())
    alt = run_simulation(scenario=scenario, strategy_name="simple2", policy=build_simple_policy())

    text = delta_table(base, alt)
    assert "Отгружено щитов" in text
    assert "Простой C3" in text

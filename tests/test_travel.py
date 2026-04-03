from __future__ import annotations

from app.config.defaults import build_default_day_scenario


def test_travel_times_are_configured() -> None:
    scenario = build_default_day_scenario()
    assert scenario.travel_time_overrides_min[("S", "C1")] == 6.0
    assert scenario.travel_time_overrides_min[("C1", "C2")] == 6.0
    assert scenario.travel_time_overrides_min[("C2", "C3")] == 6.0
    assert scenario.travel_time_overrides_min[("C3", "C4")] == 10.0
    assert scenario.travel_time_overrides_min[("C4", "P")] == 6.0


def test_shift_start_time_exists() -> None:
    scenario = build_default_day_scenario()
    assert scenario.shift_start_hhmm == "08:00"

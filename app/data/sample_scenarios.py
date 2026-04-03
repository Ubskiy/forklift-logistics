"""Built-in sample scenarios."""

from __future__ import annotations

from app.config.defaults import build_default_day_scenario, build_default_night_scenario
from app.domain.scenario import Scenario


def get_sample_scenarios() -> dict[str, Scenario]:
    """Return named sample scenarios."""

    day = build_default_day_scenario()
    night = build_default_night_scenario()
    return {
        day.name: day,
        night.name: night,
    }

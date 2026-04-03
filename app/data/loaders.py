"""Scenario loader facade."""

from __future__ import annotations

from pathlib import Path

from app.config.settings import load_scenario_by_name, load_scenario_from_json
from app.domain.scenario import Scenario


def load_scenario(name: str | None = None, json_path: str | Path | None = None) -> Scenario:
    """Load scenario either by built-in name or JSON file path."""

    if json_path is not None:
        return load_scenario_from_json(json_path)
    if name is None:
        name = "sample_day"
    return load_scenario_by_name(name)

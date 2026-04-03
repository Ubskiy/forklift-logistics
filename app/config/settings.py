"""Загрузка сценариев: встроенные и из JSON."""

from __future__ import annotations

from dataclasses import asdict
import json
from pathlib import Path
from typing import Any

from app.config.defaults import build_default_day_scenario, build_default_night_scenario
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
)


def load_scenario_by_name(name: str) -> Scenario:
    normalized = name.strip().lower()
    if normalized in {"sample_day", "day"}:
        return build_default_day_scenario()
    if normalized in {"sample_night", "night"}:
        return build_default_night_scenario()
    raise ValueError(f"Unknown scenario name: {name}")


def scenario_to_dict(scenario: Scenario) -> dict[str, Any]:
    payload = asdict(scenario)
    payload["shift_type"] = scenario.shift_type.value

    payload["travel_distances_m"] = {
        f"{a}->{b}": val for (a, b), val in scenario.travel_distances_m.items()
    }
    payload["travel_time_overrides_min"] = {
        f"{a}->{b}": val for (a, b), val in scenario.travel_time_overrides_min.items()
    }
    return payload


def _parse_edge_map(raw: dict[str, float]) -> dict[tuple[str, str], float]:
    parsed: dict[tuple[str, str], float] = {}
    for key, value in raw.items():
        if "->" not in key:
            continue
        src, dst = key.split("->", maxsplit=1)
        parsed[(src.strip(), dst.strip())] = float(value)
    return parsed


def _objective_from_raw(raw: dict[str, Any]) -> ObjectiveWeights:
    if not raw:
        return ObjectiveWeights()

    # Backward-compatible map со старых ключей.
    if "w1_makespan" in raw:
        return ObjectiveWeights(
            underproduction_penalty=float(raw.get("underproduction_penalty", 15000.0)),
            makespan_weight=float(raw.get("w1_makespan", 1.0)),
            c3_starvation_weight=float(raw.get("w3_c3_starvation", 25.0)),
            forklift_idle_weight=float(raw.get("w2_forklift_idle", 4.0)),
            wip_weight=float(raw.get("w5_excessive_wip", 6.0)),
            route_fragmentation_weight=float(raw.get("route_fragmentation_weight", 2.0)),
            violation_penalty_weight=float(raw.get("w6_violation", 100000.0)),
        )

    return ObjectiveWeights(**raw)


def scenario_from_dict(data: dict[str, Any]) -> Scenario:
    return Scenario(
        name=str(data["name"]),
        shift_type=ShiftType(str(data["shift_type"])),
        shift_duration_hours=float(data["shift_duration_hours"]),
        shift_start_hhmm=str(data.get("shift_start_hhmm", "08:00")),
        order_shields_qty=int(data["order_shields_qty"]),
        forklift=ForkliftConfig(**data["forklift"]),
        handling=HandlingTimes(**data["handling"]),
        production=ProductionRates(**data["production"]),
        objective=_objective_from_raw(data.get("objective", {})),
        sa=SAConfig(**data.get("sa", {})),
        batches=BatchSettings(**data.get("batches", {})),
        buffers=BufferSettings(**data.get("buffers", {})),
        pipes=PipeConsumption(**data.get("pipes", {})),
        tube_unit_weight_kg=float(data.get("tube_unit_weight_kg", 120.0)),
        shield_unit_weight_kg=float(data.get("shield_unit_weight_kg", 160.0)),
        initial_tubes_at_c1=int(data.get("initial_tubes_at_c1", 0)),
        initial_shields_waiting_c2=int(data.get("initial_shields_waiting_c2", 0)),
        initial_shields_waiting_c3=int(data.get("initial_shields_waiting_c3", 0)),
        initial_finished_waiting_c4=int(data.get("initial_finished_waiting_c4", 0)),
        travel_distances_m=_parse_edge_map(data.get("travel_distances_m", {})),
        travel_time_overrides_min=_parse_edge_map(data.get("travel_time_overrides_min", {})),
        max_overtime_min=float(data.get("max_overtime_min", 240.0)),
        random_seed=int(data.get("random_seed", 42)),
    )


def load_scenario_from_json(path: str | Path) -> Scenario:
    with Path(path).open("r", encoding="utf-8") as fh:
        raw = json.load(fh)
    return scenario_from_dict(raw)

"""Описание входного сценария (условий расчёта)."""

from __future__ import annotations

from dataclasses import dataclass, field
from math import ceil
from typing import Mapping

from app.domain.enums import ShiftType


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
    # Временные инженерные допущения v1 (вынесены в конфиг).
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
    """Веса целевой функции.

    Логика: недовыпуск доминирует, остальные метрики сравнивают решения
    с одинаковой отгрузкой.
    """

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
    # Буферы сделаны компактными, чтобы стратегии заметно различались.
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
    """Сценарий = все условия одного расчёта."""

    name: str
    shift_type: ShiftType
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
    travel_distances_m: dict[tuple[str, str], float] = field(default_factory=dict)
    travel_time_overrides_min: dict[tuple[str, str], float] = field(default_factory=dict)
    max_overtime_min: float = 240.0
    random_seed: int = 42

    def shift_duration_min(self) -> float:
        return self.shift_duration_hours * 60.0

    def required_tubes_for_order(self) -> int:
        return ceil(self.order_shields_qty * self.pipes.total_pipes_per_shield)


def build_travel_distances(base: Mapping[tuple[str, str], float]) -> dict[tuple[str, str], float]:
    matrix: dict[tuple[str, str], float] = {}
    for (src, dst), dist in base.items():
        matrix[(src, dst)] = dist
        matrix.setdefault((dst, src), dist)
    return matrix


def build_time_overrides(base: Mapping[tuple[str, str], float]) -> dict[tuple[str, str], float]:
    matrix: dict[tuple[str, str], float] = {}
    for (src, dst), minutes in base.items():
        matrix[(src, dst)] = minutes
        matrix.setdefault((dst, src), minutes)
    return matrix

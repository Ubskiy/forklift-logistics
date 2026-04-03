"""Доменные сущности результата симуляции."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class TripRecord:
    """Один выполненный рейс погрузчика с явными временными интервалами."""

    strategy_name: str
    forklift_id: str
    trip_id: int
    cargo_type: str
    route_from: str
    route_to: str
    qty: float
    unit_weight: float
    total_weight: float
    start_time_min: float
    load_start_min: float
    load_end_min: float
    travel_start_min: float
    travel_end_min: float
    unload_start_min: float
    unload_end_min: float
    end_time_min: float
    duration_minutes: float
    was_idle_before_trip: bool
    idle_before_trip_minutes: float

    @property
    def route(self) -> str:
        return f"{self.route_from}->{self.route_to}"


@dataclass
class RouteStats:
    """Агрегированная статистика по маршруту."""

    route: str
    trips_count: int
    total_units: float
    shields_qty: float
    tubes_qty: float
    total_weight_kg: float
    total_duration_min: float
    avg_trip_size: float
    trips_share_pct: float
    volume_share_pct: float
    busy_time_min: float


@dataclass
class SimulationMetrics:
    """Ключевые метрики для сравнения стратегий."""

    makespan_min: float = 0.0
    total_forklift_idle_min: float = 0.0
    forklift_idle_by_id: dict[str, float] = field(default_factory=dict)
    c3_starvation_min: float = 0.0
    total_shop_starvation_min: float = 0.0
    shortfall_qty: float = 0.0
    violation_count: int = 0
    moved_tubes: float = 0.0
    moved_shields: float = 0.0
    shipped_qty: float = 0.0
    trips_total: int = 0
    avg_trip_load_units: float = 0.0
    avg_trip_load_factor: float = 0.0
    avg_forklift_utilization: float = 0.0
    excessive_wip_penalty: float = 0.0
    route_fragmentation_penalty: float = 0.0
    objective_value: float = 0.0


@dataclass
class SimulationResult:
    """Результат одного прогона симуляции."""

    strategy_name: str
    metrics: SimulationMetrics
    trip_records: list[TripRecord] = field(default_factory=list)
    route_stats: list[RouteStats] = field(default_factory=list)
    meta: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "strategy_name": self.strategy_name,
            "metrics": asdict(self.metrics),
            "trip_records": [asdict(item) for item in self.trip_records],
            "route_stats": [asdict(item) for item in self.route_stats],
            "meta": dict(self.meta),
        }

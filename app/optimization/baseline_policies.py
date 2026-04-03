"""Базовые стратегии диспетчеризации."""

from __future__ import annotations

from app.simulation.simulator import BatchOverride, DispatchPolicy, ROUTE_SEQUENCE


def build_simple_policy() -> DispatchPolicy:
    """Простая стратегия: приоритет upstream (намеренно наивная)."""

    return DispatchPolicy(route_order=ROUTE_SEQUENCE)


def build_bottleneck_first_policy(batch: BatchOverride | None = None) -> DispatchPolicy:
    """Стартовая стратегия для отжига: сначала поддержка узкого места и отгрузки."""

    return DispatchPolicy(
        route_order=("C4->P", "C3->C4", "C2->C3", "C1->C2", "S->C1"),
        batch_override=batch,
    )

"""Расчёт целевой функции с доминирующим штрафом недовыпуска."""

from __future__ import annotations

from dataclasses import dataclass

from app.domain.entities import SimulationResult
from app.domain.scenario import Scenario


@dataclass
class ObjectiveBreakdown:
    shipped_qty: float
    underproduction_qty: float
    underproduction_component: float
    makespan_component: float
    c3_starvation_component: float
    forklift_idle_component: float
    wip_component: float
    fragmentation_component: float
    violation_component: float
    total: float


def evaluate_objective(result: SimulationResult, scenario: Scenario) -> ObjectiveBreakdown:
    """Целевая функция.

    objective =
        underproduction_penalty * underproduction
      + makespan_weight * makespan
      + c3_starvation_weight * c3_starvation
      + forklift_idle_weight * forklift_idle
      + wip_weight * excessive_wip
      + route_fragmentation_weight * route_fragmentation
      + violation_penalty_weight * violations
    """

    m = result.metrics
    w = scenario.objective

    underproduction = max(0.0, float(scenario.order_shields_qty) - m.shipped_qty)

    under_component = w.underproduction_penalty * underproduction
    makespan_component = w.makespan_weight * m.makespan_min
    c3_component = w.c3_starvation_weight * m.c3_starvation_min
    idle_component = w.forklift_idle_weight * m.total_forklift_idle_min
    wip_component = w.wip_weight * m.excessive_wip_penalty
    fragmentation_component = w.route_fragmentation_weight * m.route_fragmentation_penalty
    violation_component = w.violation_penalty_weight * float(m.violation_count)

    total = (
        under_component
        + makespan_component
        + c3_component
        + idle_component
        + wip_component
        + fragmentation_component
        + violation_component
    )

    m.objective_value = total
    m.shortfall_qty = underproduction

    return ObjectiveBreakdown(
        shipped_qty=m.shipped_qty,
        underproduction_qty=underproduction,
        underproduction_component=under_component,
        makespan_component=makespan_component,
        c3_starvation_component=c3_component,
        forklift_idle_component=idle_component,
        wip_component=wip_component,
        fragmentation_component=fragmentation_component,
        violation_component=violation_component,
        total=total,
    )

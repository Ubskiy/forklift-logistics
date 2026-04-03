"""Имитация отжига для подбора порядка маршрутов и размеров партий."""

from __future__ import annotations

from dataclasses import dataclass, field
import math
import random
from typing import Any

from app.domain.scenario import Scenario
from app.optimization.baseline_policies import build_bottleneck_first_policy
from app.optimization.objective import evaluate_objective
from app.simulation.simulator import BatchOverride, DispatchPolicy, run_simulation


@dataclass(frozen=True)
class PolicyCandidate:
    route_order: tuple[str, ...]
    batch: BatchOverride


@dataclass
class SAIteration:
    iteration: int
    temperature: float
    current_objective: float
    best_objective: float


@dataclass
class SAResult:
    best_candidate: PolicyCandidate
    best_policy: DispatchPolicy
    best_result: Any
    best_objective: float
    iterations_done: int
    history: list[SAIteration] = field(default_factory=list)


def _as_policy(candidate: PolicyCandidate) -> DispatchPolicy:
    return DispatchPolicy(route_order=candidate.route_order, batch_override=candidate.batch)


def _clamp_batch(scenario: Scenario, batch: BatchOverride) -> BatchOverride:
    tube_max = scenario.forklift.max_tubes_per_trip
    shield_max = scenario.forklift.max_shields_per_trip
    return BatchOverride(
        tubes_per_trip=max(1, min(tube_max, batch.tubes_per_trip)),
        shields_per_trip=max(1, min(shield_max, batch.shields_per_trip)),
        finished_per_trip=max(1, min(shield_max, batch.finished_per_trip)),
    )


def _mutate_route_order(order: tuple[str, ...], rng: random.Random) -> tuple[str, ...]:
    seq = list(order)

    if rng.random() < 0.55:
        i, j = sorted(rng.sample(range(len(seq)), 2))
        seq[i], seq[j] = seq[j], seq[i]
        return tuple(seq)

    i = rng.randrange(len(seq))
    j = rng.randrange(len(seq))
    item = seq.pop(i)
    seq.insert(j, item)
    return tuple(seq)


def _mutate_batch(candidate: PolicyCandidate, scenario: Scenario, rng: random.Random) -> BatchOverride:
    batch = candidate.batch
    name = rng.choice(["tubes", "shields", "finished"])
    step = rng.choice([-1, 1])

    if name == "tubes":
        batch = BatchOverride(batch.tubes_per_trip + step, batch.shields_per_trip, batch.finished_per_trip)
    elif name == "shields":
        batch = BatchOverride(batch.tubes_per_trip, batch.shields_per_trip + step, batch.finished_per_trip)
    else:
        batch = BatchOverride(batch.tubes_per_trip, batch.shields_per_trip, batch.finished_per_trip + step)

    return _clamp_batch(scenario, batch)


def _mutate(candidate: PolicyCandidate, scenario: Scenario, rng: random.Random) -> PolicyCandidate:
    if rng.random() < 0.6:
        return PolicyCandidate(route_order=_mutate_route_order(candidate.route_order, rng), batch=candidate.batch)

    return PolicyCandidate(route_order=candidate.route_order, batch=_mutate_batch(candidate, scenario, rng))


def optimize_with_sa(scenario: Scenario, seed: int | None = None) -> SAResult:
    """Запускает simulated annealing и возвращает лучшую стратегию."""

    rng = random.Random(scenario.random_seed if seed is None else seed)

    start_policy = build_bottleneck_first_policy(
        BatchOverride(
            tubes_per_trip=scenario.batches.tubes_per_trip_default,
            shields_per_trip=scenario.batches.shields_per_trip_default,
            finished_per_trip=scenario.batches.finished_per_trip_default,
        )
    )

    current = PolicyCandidate(
        route_order=start_policy.route_order,
        batch=start_policy.batch_override
        if start_policy.batch_override is not None
        else BatchOverride(
            tubes_per_trip=scenario.batches.tubes_per_trip_default,
            shields_per_trip=scenario.batches.shields_per_trip_default,
            finished_per_trip=scenario.batches.finished_per_trip_default,
        ),
    )

    current_policy = _as_policy(current)
    current_result = run_simulation(scenario=scenario, strategy_name="simulated_annealing", policy=current_policy)
    current_obj = evaluate_objective(current_result, scenario).total

    best = current
    best_policy = current_policy
    best_result = current_result
    best_obj = current_obj

    temperature = scenario.sa.initial_temperature
    history: list[SAIteration] = []
    iterations_done = 0

    for i in range(scenario.sa.iterations):
        iterations_done = i + 1
        if temperature < scenario.sa.min_temperature:
            break

        neighbor = _mutate(current, scenario, rng)
        neighbor_policy = _as_policy(neighbor)
        neighbor_result = run_simulation(scenario=scenario, strategy_name="simulated_annealing", policy=neighbor_policy)
        neighbor_obj = evaluate_objective(neighbor_result, scenario).total

        delta = neighbor_obj - current_obj
        if delta <= 0:
            accept = True
        else:
            accept = rng.random() < math.exp(-delta / max(temperature, 1e-9))

        if accept:
            current = neighbor
            current_policy = neighbor_policy
            current_result = neighbor_result
            current_obj = neighbor_obj

        if current_obj < best_obj:
            best = current
            best_policy = current_policy
            best_result = current_result
            best_obj = current_obj

        history.append(
            SAIteration(
                iteration=i,
                temperature=temperature,
                current_objective=current_obj,
                best_objective=best_obj,
            )
        )

        temperature *= scenario.sa.cooling_rate

    return SAResult(
        best_candidate=best,
        best_policy=best_policy,
        best_result=best_result,
        best_objective=best_obj,
        iterations_done=iterations_done,
        history=history,
    )

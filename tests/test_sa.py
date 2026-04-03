from __future__ import annotations

from app.config.defaults import build_default_day_scenario
from app.optimization.baseline_policies import build_simple_policy
from app.optimization.objective import evaluate_objective
from app.optimization.simulated_annealing import optimize_with_sa
from app.simulation.simulator import run_simulation


def test_sa_reproducible_with_same_seed() -> None:
    scenario = build_default_day_scenario()
    scenario.sa.iterations = 60

    r1 = optimize_with_sa(scenario, seed=123)
    r2 = optimize_with_sa(scenario, seed=123)

    assert r1.best_objective == r2.best_objective
    assert r1.best_candidate == r2.best_candidate


def test_sa_not_worse_than_simple_on_demo_scenario() -> None:
    scenario = build_default_day_scenario()
    scenario.sa.iterations = 120

    baseline = run_simulation(scenario=scenario, strategy_name="simple", policy=build_simple_policy())
    baseline_obj = evaluate_objective(baseline, scenario).total

    sa = optimize_with_sa(scenario=scenario, seed=42)
    sa_obj = evaluate_objective(sa.best_result, scenario).total

    assert sa_obj <= baseline_obj

"""Компактный CLI проекта."""

from __future__ import annotations

import argparse
from pathlib import Path

from app.core import (
    ascii_timeline,
    build_simple_policy,
    delta_table,
    evaluate_objective,
    format_minutes_hms,
    load_scenario,
    optimize_with_sa,
    route_stats_table,
    run_simulation,
    save_forklift_timeline_plot,
    trip_log_table,
)


def _summary_block(title: str, result) -> str:
    m = result.metrics
    objective_breakdown = result.meta.get("objective_breakdown", {})
    lines = [
        f"[{title}]",
        f"  Целевая функция: {m.objective_value:.2f}",
        f"  Общее время: {format_minutes_hms(m.makespan_min)}",
        f"  Отгружено щитов: {m.shipped_qty:.1f}",
        f"  Недовыпуск: {m.shortfall_qty:.1f}",
        f"  Простой C3: {format_minutes_hms(m.c3_starvation_min)}",
        f"  Суммарный простой погрузчиков: {format_minutes_hms(m.total_forklift_idle_min)}",
        f"  Число рейсов: {m.trips_total}",
        f"  Перевезено труб: {m.moved_tubes:.1f}",
        f"  Отгружено щитов рейсами C4->P: {m.moved_shields:.1f}",
        f"  Средняя партия: {m.avg_trip_load_units:.2f}",
        f"  Средняя загрузка рейса: {100.0 * m.avg_trip_load_factor:.1f}%",
        f"  Средняя загрузка погрузчиков: {100.0 * m.avg_forklift_utilization:.1f}%",
    ]
    if objective_breakdown:
        lines.extend(
            [
                f"  objective: штраф недовыпуска = {objective_breakdown.get('underproduction_component', 0.0):.1f}",
                f"  objective: вклад C3-простоя = {objective_breakdown.get('c3_starvation_component', 0.0):.1f}",
                f"  objective: вклад простоя погрузчиков = {objective_breakdown.get('forklift_idle_component', 0.0):.1f}",
            ]
        )
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Сравнение стратегий внутризаводской логистики")
    parser.add_argument("mode", nargs="?", default="compare", choices=["baseline", "sa", "compare"])
    parser.add_argument("--scenario", default="sample_day")
    parser.add_argument("--iterations", type=int, default=200)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--show-trip-log", action="store_true")
    parser.add_argument("--show-route-stats", action="store_true")
    parser.add_argument("--show-delta", action="store_true")
    parser.add_argument("--plot", action="store_true")
    parser.add_argument("--plot-timeline-only", action="store_true")
    parser.add_argument("--plot-dir", default="artifacts/plots")
    return parser


def _run_baseline(scenario):
    result = run_simulation(scenario=scenario, strategy_name="simple", policy=build_simple_policy())
    evaluate_objective(result, scenario)
    return result


def _run_sa(scenario):
    sa = optimize_with_sa(scenario=scenario, seed=scenario.random_seed)
    evaluate_objective(sa.best_result, scenario)
    return sa


def _save_timeline_plot(result, scenario, output_file: Path, title: str) -> Path:
    return save_forklift_timeline_plot(result, output_file, shift_start_hhmm=scenario.shift_start_hhmm, title=title)


def main() -> None:
    args = build_parser().parse_args()

    scenario = load_scenario(name=args.scenario)
    scenario.random_seed = args.seed
    scenario.sa.iterations = args.iterations

    print(f"Сценарий: {scenario.name}")
    print(f"Смена: старт {scenario.shift_start_hhmm}, длительность {scenario.shift_duration_hours:.1f} ч")

    if args.mode == "baseline":
        base = _run_baseline(scenario)
        print(_summary_block("Простая стратегия", base))

        if args.show_route_stats:
            print("\n=== Простая стратегия: статистика маршрутов ===")
            print(route_stats_table(base))

        if args.show_trip_log:
            print("\n=== Простая стратегия: журнал рейсов ===")
            print(trip_log_table(base, scenario.shift_start_hhmm))
            print("\n=== Простая стратегия: ASCII-таймлайн ===")
            print(ascii_timeline(base, scenario.shift_start_hhmm))

        if args.plot or args.plot_timeline_only:
            out = Path(args.plot_dir)
            out.mkdir(parents=True, exist_ok=True)
            path = _save_timeline_plot(base, scenario, out / f"{scenario.name}_таймлайн_simple.png", "Простая стратегия")
            print(f"\nГрафик сохранён: {path}")
        return

    if args.mode == "sa":
        sa = _run_sa(scenario)
        res = sa.best_result
        print(_summary_block("Имитация отжига", res))
        print(f"  Итераций отжига: {sa.iterations_done}")

        if args.show_route_stats:
            print("\n=== Имитация отжига: статистика маршрутов ===")
            print(route_stats_table(res))

        if args.show_trip_log:
            print("\n=== Имитация отжига: журнал рейсов ===")
            print(trip_log_table(res, scenario.shift_start_hhmm))
            print("\n=== Имитация отжига: ASCII-таймлайн ===")
            print(ascii_timeline(res, scenario.shift_start_hhmm))

        if args.plot or args.plot_timeline_only:
            out = Path(args.plot_dir)
            out.mkdir(parents=True, exist_ok=True)
            path = _save_timeline_plot(res, scenario, out / f"{scenario.name}_таймлайн_sa.png", "Имитация отжига")
            print(f"\nГрафик сохранён: {path}")
        return

    base = _run_baseline(scenario)
    sa = _run_sa(scenario)
    sa_res = sa.best_result

    print(_summary_block("Простая стратегия", base))
    print(_summary_block("Имитация отжига", sa_res))
    print(f"  Итераций отжига: {sa.iterations_done}")

    diff = base.metrics.objective_value - sa_res.metrics.objective_value
    if diff > 0:
        print(f"\nИтог: отжиг лучше на {diff:.2f}")
    elif diff < 0:
        print(f"\nИтог: простая стратегия лучше на {abs(diff):.2f}")
    else:
        print("\nИтог: стратегии равны по objective")

    if args.show_delta:
        print("\n=== Дельта по метрикам ===")
        print(delta_table(base, sa_res))

    if args.show_route_stats:
        print("\n=== Простая стратегия: статистика маршрутов ===")
        print(route_stats_table(base))
        print("\n=== Имитация отжига: статистика маршрутов ===")
        print(route_stats_table(sa_res))

    if args.show_trip_log:
        print("\n=== Простая стратегия: журнал рейсов ===")
        print(trip_log_table(base, scenario.shift_start_hhmm))
        print("\n=== Имитация отжига: журнал рейсов ===")
        print(trip_log_table(sa_res, scenario.shift_start_hhmm))
        print("\n=== Простая стратегия: ASCII-таймлайн ===")
        print(ascii_timeline(base, scenario.shift_start_hhmm))
        print("\n=== Имитация отжига: ASCII-таймлайн ===")
        print(ascii_timeline(sa_res, scenario.shift_start_hhmm))

    if args.plot or args.plot_timeline_only:
        out = Path(args.plot_dir)
        out.mkdir(parents=True, exist_ok=True)
        p1 = _save_timeline_plot(base, scenario, out / f"{scenario.name}_таймлайн_simple.png", "Простая стратегия")
        p2 = _save_timeline_plot(sa_res, scenario, out / f"{scenario.name}_таймлайн_sa.png", "Имитация отжига")
        print(f"\nГрафики сохранены:\n  {p1}\n  {p2}")


if __name__ == "__main__":
    main()

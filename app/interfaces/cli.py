"""Компактный CLI проекта."""

from __future__ import annotations

import argparse
from pathlib import Path

from app.core import (
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
        f"  Значение целевой функции: {m.objective_value:.2f}",
        f"  Общее время: {format_minutes_hms(m.makespan_min)}",
        f"  Отгружено щитов: {m.shipped_qty:.1f}",
        f"  Недовыпуск: {m.shortfall_qty:.1f}",
        f"  Простой C3: {format_minutes_hms(m.c3_starvation_min)}",
        f"  Свободное время погрузчиков: {format_minutes_hms(m.total_forklift_idle_min)}",
        f"  Штрафуемый простой погрузчиков: {format_minutes_hms(m.avoidable_forklift_idle_min)}",
        f"  Число рейсов: {m.trips_total}",
        f"  Перевезено труб: {m.moved_tubes:.1f}",
        f"  Отгружено щитов рейсами C4->P: {m.moved_shields:.1f}",
        f"  Порожний пробег (мин): {m.empty_travel_total_min:.1f}",
        f"  Средняя партия: {m.avg_trip_load_units:.2f}",
        f"  Средняя загрузка рейса: {100.0 * m.avg_trip_load_factor:.1f}%",
        f"  Средняя загрузка погрузчиков: {100.0 * m.avg_forklift_utilization:.1f}%",
    ]
    if objective_breakdown:
        lines.extend(
            [
                f"  Вклад недовыпуска в значение целевой функции = {objective_breakdown.get('underproduction_component', 0.0):.1f}",
                f"  Вклад простоя C3 в значение целевой функции = {objective_breakdown.get('c3_starvation_component', 0.0):.1f}",
                f"  Вклад штрафуемого простоя в значение целевой функции = {objective_breakdown.get('forklift_idle_component', 0.0):.1f}",
            ]
        )
    if "schedule_size" in result.meta:
        lines.extend(
            [
                f"  Рейсов в расписании SA: {result.meta['schedule_size']}",
                f"  Изменено позиций расписания: {result.meta.get('changed_schedule_positions', 0)}",
                f"  Не выполнено до конца смены: {result.meta['unexecuted_schedule_items']}",
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
    sa = optimize_with_sa(scenario=scenario, seed=scenario.sa.seed)
    evaluate_objective(sa.best_result, scenario)
    return sa


def _print_result(title, result, scenario, args, suffix: str) -> None:
    print(_summary_block(title, result))
    if args.show_route_stats:
        print(f"\n=== {title}: статистика маршрутов ===")
        print(route_stats_table(result))
    if args.show_trip_log:
        print(f"\n=== {title}: журнал рейсов ===")
        print(trip_log_table(result, scenario.shift_start_hhmm))
    if args.plot or args.plot_timeline_only:
        path = Path(args.plot_dir) / f"{scenario.name}_таймлайн_{suffix}.png"
        save_forklift_timeline_plot(result, path, shift_start_hhmm=scenario.shift_start_hhmm, title=title)
        print(f"\nГрафик сохранён: {path}")


def main() -> None:
    args = build_parser().parse_args()

    scenario = load_scenario(name=args.scenario)
    scenario.sa.seed = args.seed
    scenario.sa.iterations = args.iterations

    print(f"Сценарий: {scenario.name}")
    print(f"Смена: старт {scenario.shift_start_hhmm}, длительность {scenario.shift_duration_hours:.1f} ч")

    if args.mode == "baseline":
        _print_result("Жадная стратегия", _run_baseline(scenario), scenario, args, "simple")
        return

    if args.mode == "sa":
        sa = _run_sa(scenario)
        _print_result("Имитация отжига", sa.best_result, scenario, args, "sa")
        print(f"  Итераций отжига: {sa.iterations_done}")
        return

    base = _run_baseline(scenario)
    sa = _run_sa(scenario)
    sa_res = sa.best_result

    _print_result("Жадная стратегия", base, scenario, args, "simple")
    _print_result("Имитация отжига", sa_res, scenario, args, "sa")
    print(f"  Итераций отжига: {sa.iterations_done}")

    diff = base.metrics.objective_value - sa_res.metrics.objective_value
    if diff > 0:
        print(f"\nИтог: отжиг лучше на {diff:.2f}")
    elif diff < 0:
        print(f"\nИтог: жадная стратегия лучше на {abs(diff):.2f}")
    else:
        print("\nИтог: стратегии имеют одинаковое значение целевой функции")

    if args.show_delta:
        print("\n=== Дельта по метрикам ===")
        print(delta_table(base, sa_res))

if __name__ == "__main__":
    main()

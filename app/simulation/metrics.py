"""Форматирование метрик и отчётов для CLI."""

from __future__ import annotations

from collections import defaultdict

from app.domain.entities import SimulationResult


def format_minutes_hms(minutes: float) -> str:
    total_seconds = max(0, int(round(minutes * 60.0)))
    hours, rem = divmod(total_seconds, 3600)
    mins, secs = divmod(rem, 60)
    return f"{hours:02d}:{mins:02d}:{secs:02d}"


def _parse_hhmm(value: str) -> int:
    hh, mm = value.split(":", maxsplit=1)
    return int(hh) * 60 + int(mm)


def format_clock_time(offset_minutes: float, shift_start_hhmm: str) -> str:
    start_min = _parse_hhmm(shift_start_hhmm)
    absolute = int(round(offset_minutes + start_min))
    hh = (absolute // 60) % 24
    mm = absolute % 60
    return f"{hh:02d}:{mm:02d}"


def format_interval(start_min: float, end_min: float, shift_start_hhmm: str) -> str:
    return f"{format_clock_time(start_min, shift_start_hhmm)}-{format_clock_time(end_min, shift_start_hhmm)}"


def summary_metrics(result: SimulationResult) -> dict[str, float]:
    m = result.metrics
    return {
        "objective": m.objective_value,
        "makespan_min": m.makespan_min,
        "shipped_qty": m.shipped_qty,
        "shortfall_qty": m.shortfall_qty,
        "c3_starvation_min": m.c3_starvation_min,
        "forklift_idle_min": m.total_forklift_idle_min,
        "trips_total": float(m.trips_total),
        "avg_trip_qty": m.avg_trip_load_units,
        "avg_trip_load_factor_pct": 100.0 * m.avg_trip_load_factor,
        "avg_forklift_utilization_pct": 100.0 * m.avg_forklift_utilization,
    }


def route_stats_table(result: SimulationResult) -> str:
    lines = [
        "Маршрут | Рейсов | Щитов | Труб | Вес, кг | Время, мин | Ср. партия | % рейсов | % объёма",
        "-----------------------------------------------------------------------------------------",
    ]

    if not result.route_stats:
        lines.append("(нет рейсов)")
        return "\n".join(lines)

    for row in result.route_stats:
        lines.append(
            (
                f"{row.route:7s} | {row.trips_count:6d} | {row.shields_qty:5.1f} | {row.tubes_qty:4.1f} | "
                f"{row.total_weight_kg:7.0f} | {row.total_duration_min:10.1f} | {row.avg_trip_size:10.2f} | "
                f"{row.trips_share_pct:7.2f}% | {row.volume_share_pct:7.2f}%"
            )
        )

    return "\n".join(lines)


def trip_log_table(result: SimulationResult, shift_start_hhmm: str) -> str:
    lines = []
    if not result.trip_records:
        return "(рейсов нет)"

    for trip in result.trip_records:
        interval = format_interval(trip.start_time_min, trip.end_time_min, shift_start_hhmm)
        load_interval = format_interval(trip.load_start_min, trip.load_end_min, shift_start_hhmm)
        travel_interval = format_interval(trip.travel_start_min, trip.travel_end_min, shift_start_hhmm)
        unload_interval = format_interval(trip.unload_start_min, trip.unload_end_min, shift_start_hhmm)
        lines.append(
            (
                f"{interval} | {trip.forklift_id:4s} | {trip.route:7s} | {trip.cargo_type:13s} | "
                f"qty={trip.qty:4.0f} | {trip.total_weight:6.0f} кг | "
                f"погр:{load_interval} | путь:{travel_interval} | выгр:{unload_interval} | "
                f"idle_before={trip.idle_before_trip_minutes:5.1f} мин"
            )
        )
    return "\n".join(lines)


def delta_table(base: SimulationResult, alt: SimulationResult) -> str:
    base_m = summary_metrics(base)
    alt_m = summary_metrics(alt)

    rows = [
        ("Отгружено щитов", "shipped_qty", False),
        ("Недовыпуск", "shortfall_qty", True),
        ("Общее время, мин", "makespan_min", True),
        ("Простой C3, мин", "c3_starvation_min", True),
        ("Простой погрузчиков, мин", "forklift_idle_min", True),
        ("Число рейсов", "trips_total", True),
        ("Средняя партия", "avg_trip_qty", False),
        ("Средняя загрузка рейса, %", "avg_trip_load_factor_pct", False),
        ("Средняя загрузка погрузчиков, %", "avg_forklift_utilization_pct", False),
        ("Целевая функция", "objective", True),
    ]

    lines = [
        "Показатель | Простая | Отжиг | Разница (Отжиг-Простая)",
        "---------------------------------------------------------",
    ]

    for title, key, _ in rows:
        b = base_m[key]
        a = alt_m[key]
        lines.append(f"{title:30s} | {b:8.2f} | {a:8.2f} | {a - b:10.2f}")

    return "\n".join(lines)


def ascii_timeline(result: SimulationResult, shift_start_hhmm: str, width: int = 80) -> str:
    """Простой ASCII-таймлайн занятости погрузчиков."""

    if not result.trip_records:
        return "(рейсов нет)"

    makespan = max(item.end_time_min for item in result.trip_records)
    if makespan <= 0:
        return "(рейсов нет)"

    buckets = max(20, width)

    per_forklift: dict[str, list[str]] = defaultdict(lambda: ["." for _ in range(buckets)])

    route_char = {
        "S->C1": "S",
        "C1->C2": "1",
        "C2->C3": "2",
        "C3->C4": "3",
        "C4->P": "P",
    }

    for trip in result.trip_records:
        start_idx = int((trip.start_time_min / makespan) * (buckets - 1))
        end_idx = int((trip.end_time_min / makespan) * (buckets - 1))
        marker = route_char.get(trip.route, "#")
        for idx in range(max(0, start_idx), min(buckets, end_idx + 1)):
            per_forklift[trip.forklift_id][idx] = marker

    lines = [
        f"Таймлайн {shift_start_hhmm} -> {format_clock_time(makespan, shift_start_hhmm)}",
        "Легенда: S=S->C1, 1=C1->C2, 2=C2->C3, 3=C3->C4, P=C4->P, .=простой",
    ]

    for forklift_id in sorted(per_forklift):
        lines.append(f"{forklift_id:4s} | {''.join(per_forklift[forklift_id])}")

    return "\n".join(lines)


# Backward-compatible alias.
def simple_route_table(result: SimulationResult) -> str:
    return route_stats_table(result)

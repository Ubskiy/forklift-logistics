"""Визуализация: только полезный график таймлайна погрузчиков (Gantt-like)."""

from __future__ import annotations

import contextlib
import io
from pathlib import Path

from app.domain.entities import SimulationResult
from app.simulation.metrics import format_clock_time


def _matplotlib():
    stderr_buffer = io.StringIO()
    stdout_buffer = io.StringIO()
    with contextlib.redirect_stderr(stderr_buffer), contextlib.redirect_stdout(stdout_buffer):
        try:
            import matplotlib.pyplot as plt  # type: ignore
        except Exception:
            raise RuntimeError(
                "Matplotlib недоступен в этом окружении. "
                "Установите или переустановите matplotlib в активном venv."
            ) from None
    return plt


def save_forklift_timeline_plot(
    result: SimulationResult,
    output_path: str | Path,
    *,
    shift_start_hhmm: str,
    title: str | None = None,
) -> Path:
    plt = _matplotlib()

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)

    trips = result.trip_records
    if not trips:
        fig, ax = plt.subplots(figsize=(10, 3))
        ax.set_title(title or f"{result.strategy_name}: таймлайн погрузчиков")
        ax.text(0.5, 0.5, "Рейсы отсутствуют", ha="center", va="center", transform=ax.transAxes)
        ax.axis("off")
        fig.tight_layout()
        fig.savefig(output, dpi=140)
        plt.close(fig)
        return output

    routes = ["S->C1", "C1->C2", "C2->C3", "C3->C4", "C4->P"]
    route_color = {
        "S->C1": "#4C78A8",
        "C1->C2": "#F58518",
        "C2->C3": "#54A24B",
        "C3->C4": "#E45756",
        "C4->P": "#72B7B2",
    }

    forklifts = sorted({item.forklift_id for item in trips})
    y_map = {forklift_id: idx for idx, forklift_id in enumerate(forklifts)}

    max_time = max(item.end_time_min for item in trips)
    fig_height = max(3.4, 1.1 * len(forklifts) + 1.8)
    fig, ax = plt.subplots(figsize=(14, fig_height))

    bar_h = 0.55
    for trip in trips:
        y = y_map[trip.forklift_id]
        color = route_color.get(trip.route, "#777777")
        ax.broken_barh([(trip.start_time_min, trip.duration_minutes)], (y - bar_h / 2, bar_h), facecolors=color, alpha=0.9)

        if trip.duration_minutes >= 7.0:
            ax.text(
                trip.start_time_min + trip.duration_minutes / 2,
                y,
                trip.route,
                color="white",
                ha="center",
                va="center",
                fontsize=8,
                fontweight="bold",
            )

    ax.set_yticks(list(y_map.values()))
    ax.set_yticklabels(forklifts)
    ax.set_ylabel("Погрузчик")

    tick_step = 60 if max_time > 180 else 30
    xticks = list(range(0, int(max_time) + tick_step, tick_step))
    ax.set_xticks(xticks)
    ax.set_xticklabels([format_clock_time(float(tick), shift_start_hhmm) for tick in xticks], rotation=0)
    ax.set_xlabel("Время")

    legend_handles = [
        plt.Line2D([0], [0], color=route_color[route], lw=8, label=route) for route in routes
    ]
    ax.legend(handles=legend_handles, title="Маршрут", ncol=5, frameon=False, loc="upper center", bbox_to_anchor=(0.5, 1.16))

    ax.set_xlim(0, max(1.0, max_time))
    ax.grid(axis="x", alpha=0.25)
    ax.set_title(title or f"{result.strategy_name}: таймлайн погрузчиков")

    fig.tight_layout()
    fig.savefig(output, dpi=150)
    plt.close(fig)
    return output

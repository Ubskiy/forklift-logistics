"""Минимальный desktop-интерфейс (Tkinter) для демонстрации результата."""

from __future__ import annotations

import threading
from pathlib import Path
import tkinter as tk
from tkinter import messagebox, ttk

from app.data.loaders import load_scenario
from app.interfaces.visualization import save_forklift_timeline_plot
from app.optimization.baseline_policies import build_simple_policy
from app.optimization.objective import evaluate_objective
from app.optimization.simulated_annealing import optimize_with_sa
from app.simulation.metrics import format_minutes_hms, route_stats_table
from app.simulation.simulator import run_simulation


def _summary_text(result) -> str:
    m = result.metrics
    return "\n".join(
        [
            f"Целевая функция: {m.objective_value:.2f}",
            f"Общее время: {format_minutes_hms(m.makespan_min)}",
            f"Отгружено щитов: {m.shipped_qty:.1f}",
            f"Недовыпуск: {m.shortfall_qty:.1f}",
            f"Простой C3: {format_minutes_hms(m.c3_starvation_min)}",
            f"Простой погрузчиков: {format_minutes_hms(m.total_forklift_idle_min)}",
            f"Число рейсов: {m.trips_total}",
        ]
    )


class DesktopApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Логистика: сравнение стратегий")
        self.root.geometry("980x720")

        self.scenario_var = tk.StringVar(value="sample_day")
        self.iter_var = tk.StringVar(value="200")
        self.seed_var = tk.StringVar(value="42")
        self.plot_var = tk.BooleanVar(value=True)
        self.plot_dir_var = tk.StringVar(value="artifacts/plots")
        self.status_var = tk.StringVar(value="Готово")

        self._build_ui()

    def _build_ui(self) -> None:
        top = ttk.Frame(self.root, padding=10)
        top.pack(fill=tk.X)

        ttk.Label(top, text="Сценарий").grid(row=0, column=0, sticky=tk.W)
        ttk.Combobox(top, textvariable=self.scenario_var, values=["sample_day", "sample_night"], width=14, state="readonly").grid(row=1, column=0, padx=(0, 8), sticky=tk.W)

        ttk.Label(top, text="Итераций отжига").grid(row=0, column=1, sticky=tk.W)
        ttk.Entry(top, textvariable=self.iter_var, width=9).grid(row=1, column=1, padx=(0, 8), sticky=tk.W)

        ttk.Label(top, text="Seed").grid(row=0, column=2, sticky=tk.W)
        ttk.Entry(top, textvariable=self.seed_var, width=9).grid(row=1, column=2, padx=(0, 8), sticky=tk.W)

        ttk.Checkbutton(top, text="Сохранить графики", variable=self.plot_var).grid(row=1, column=3, padx=(0, 8), sticky=tk.W)

        ttk.Label(top, text="Папка графиков").grid(row=0, column=4, sticky=tk.W)
        ttk.Entry(top, textvariable=self.plot_dir_var, width=24).grid(row=1, column=4, padx=(0, 8), sticky=tk.W)

        ttk.Button(top, text="Запустить сравнение", command=self._run).grid(row=1, column=5, sticky=tk.W)

        self.output = tk.Text(self.root, wrap=tk.WORD, font=("Menlo", 11))
        self.output.pack(fill=tk.BOTH, expand=True, padx=10, pady=8)

        ttk.Label(self.root, textvariable=self.status_var, anchor=tk.W, padding=(10, 2)).pack(fill=tk.X)

    def _set_text(self, text: str) -> None:
        self.output.delete("1.0", tk.END)
        self.output.insert(tk.END, text)

    def _run(self) -> None:
        try:
            iterations = int(self.iter_var.get())
            seed = int(self.seed_var.get())
            if iterations <= 0:
                raise ValueError
        except ValueError:
            messagebox.showerror("Ошибка", "Введите целые положительные значения")
            return

        self.status_var.set("Расчёт...")
        self._set_text("Идёт расчёт...")

        thread = threading.Thread(
            target=self._compute,
            args=(self.scenario_var.get(), iterations, seed, self.plot_var.get(), self.plot_dir_var.get()),
            daemon=True,
        )
        thread.start()

    def _compute(self, scenario_name: str, iterations: int, seed: int, save_plot: bool, plot_dir: str) -> None:
        try:
            scenario = load_scenario(name=scenario_name)
            scenario.random_seed = seed
            scenario.sa.iterations = iterations

            baseline = run_simulation(scenario=scenario, strategy_name="simple", policy=build_simple_policy())
            evaluate_objective(baseline, scenario)

            sa = optimize_with_sa(scenario=scenario, seed=seed)
            evaluate_objective(sa.best_result, scenario)

            diff = baseline.metrics.objective_value - sa.best_result.metrics.objective_value
            if diff > 0:
                final_line = f"Итог: отжиг лучше на {diff:.2f}"
            elif diff < 0:
                final_line = f"Итог: простая стратегия лучше на {abs(diff):.2f}"
            else:
                final_line = "Итог: равенство"

            lines = [
                f"Сценарий: {scenario.name}",
                "",
                "Простая стратегия:",
                _summary_text(baseline),
                "",
                "Имитация отжига:",
                _summary_text(sa.best_result),
                f"Итераций: {sa.iterations_done}",
                "",
                final_line,
                "",
                "Маршруты (отжиг):",
                route_stats_table(sa.best_result),
            ]

            if save_plot:
                out = Path(plot_dir)
                out.mkdir(parents=True, exist_ok=True)
                p1 = save_forklift_timeline_plot(
                    baseline,
                    out / f"{scenario.name}_таймлайн_simple.png",
                    shift_start_hhmm=scenario.shift_start_hhmm,
                    title="Простая стратегия",
                )
                p2 = save_forklift_timeline_plot(
                    sa.best_result,
                    out / f"{scenario.name}_таймлайн_sa.png",
                    shift_start_hhmm=scenario.shift_start_hhmm,
                    title="Имитация отжига",
                )
                lines.extend(["", "Графики:", str(p1), str(p2)])

            text = "\n".join(lines)
            self.root.after(0, lambda: self._finish_ok(text))
        except Exception as exc:
            self.root.after(0, lambda: self._finish_error(str(exc)))

    def _finish_ok(self, text: str) -> None:
        self._set_text(text)
        self.status_var.set("Готово")

    def _finish_error(self, msg: str) -> None:
        self._set_text(f"Ошибка:\n{msg}")
        self.status_var.set("Ошибка")
        messagebox.showerror("Ошибка", msg)


def main() -> None:
    root = tk.Tk()
    DesktopApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()

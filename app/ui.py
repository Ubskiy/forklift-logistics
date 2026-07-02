"""Streamlit UI для интерактивного сравнения стратегий логистики."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import streamlit as st

from app.core import (
    ROUTE_SEQUENCE,
    build_simple_policy,
    delta_table,
    evaluate_objective,
    format_clock_time,
    format_interval,
    format_minutes_hms,
    load_scenario,
    optimize_with_sa,
    run_simulation,
    save_forklift_timeline_plot,
)


def _set_travel_bidirectional(scenario, src: str, dst: str, value_min: float) -> None:
    scenario.travel_time_overrides_min[(src, dst)] = float(value_min)
    scenario.travel_time_overrides_min[(dst, src)] = float(value_min)


def _summary_rows(result, breakdown: dict) -> list[dict[str, str]]:
    m = result.metrics
    rows = [
        {"Показатель": "Значение целевой функции", "Значение": f"{m.objective_value:.2f}"},
        {"Показатель": "Общее время", "Значение": format_minutes_hms(m.makespan_min)},
        {"Показатель": "Отгружено щитов", "Значение": f"{m.shipped_qty:.1f}"},
        {"Показатель": "Недовыпуск", "Значение": f"{m.shortfall_qty:.1f}"},
        {"Показатель": "Простой C3", "Значение": format_minutes_hms(m.c3_starvation_min)},
        {"Показатель": "Свободное время погрузчиков", "Значение": format_minutes_hms(m.total_forklift_idle_min)},
        {"Показатель": "Штрафуемый простой погрузчиков", "Значение": format_minutes_hms(m.avoidable_forklift_idle_min)},
        {"Показатель": "Порожний пробег (мин)", "Значение": f"{m.empty_travel_total_min:.1f}"},
        {"Показатель": "Число рейсов", "Значение": f"{m.trips_total}"},
        {"Показатель": "Средняя партия", "Значение": f"{m.avg_trip_load_units:.2f}"},
        {"Показатель": "Средняя загрузка рейса", "Значение": f"{100.0 * m.avg_trip_load_factor:.1f}%"},
        {"Показатель": "Средняя загрузка погрузчиков", "Значение": f"{100.0 * m.avg_forklift_utilization:.1f}%"},
        {"Показатель": "Штраф недовыпуска", "Значение": f"{breakdown['underproduction_component']:.1f}"},
        {"Показатель": "Вклад простоя C3", "Значение": f"{breakdown['c3_starvation_component']:.1f}"},
        {"Показатель": "Вклад штрафуемого простоя", "Значение": f"{breakdown['forklift_idle_component']:.1f}"},
    ]
    if "schedule_size" in result.meta:
        rows.extend(
            [
                {"Показатель": "Рейсов в расписании SA", "Значение": str(result.meta["schedule_size"])},
                {"Показатель": "Изменено позиций расписания", "Значение": str(result.meta.get("changed_schedule_positions", 0))},
                {"Показатель": "Не выполнено до конца смены", "Значение": str(result.meta["unexecuted_schedule_items"])},
            ]
        )
    return rows


def _route_rows(result) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for r in result.route_stats:
        rows.append(
            {
                "Маршрут": r.route,
                "Рейсов": str(r.trips_count),
                "Щитов": f"{r.shields_qty:.1f}",
                "Труб": f"{r.tubes_qty:.1f}",
                "Вес, кг": f"{r.total_weight_kg:.0f}",
                "Время, мин": f"{r.total_duration_min:.1f}",
                "Ср. партия": f"{r.avg_trip_size:.2f}",
                "% рейсов": f"{r.trips_share_pct:.1f}",
                "% объёма": f"{r.volume_share_pct:.1f}",
            }
        )
    return rows


def _trip_rows(result, shift_start_hhmm: str) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for trip in result.trip_records:
        rows.append(
            {
                "Интервал": format_interval(trip.start_time_min, trip.end_time_min, shift_start_hhmm),
                "Погрузчик": trip.forklift_id,
                "Маршрут": trip.route,
                "Груз": trip.cargo_type,
                "Кол-во": f"{trip.qty:.0f}",
                "Вес, кг": f"{trip.total_weight:.0f}",
                "Порожний перегон, мин": f"{trip.empty_travel_minutes:.1f}",
                "Погрузка": format_interval(trip.load_start_min, trip.load_end_min, shift_start_hhmm),
                "Движение": format_interval(trip.travel_start_min, trip.travel_end_min, shift_start_hhmm),
                "Выгрузка": format_interval(trip.unload_start_min, trip.unload_end_min, shift_start_hhmm),
                "Простой до рейса, мин": f"{trip.idle_before_trip_minutes:.1f}",
            }
        )
    return rows


def _timeline_image(result, scenario, suffix: str, title: str) -> Path:
    out = Path("artifacts/plots")
    out.mkdir(parents=True, exist_ok=True)
    path = out / f"{scenario.name}_ui_{suffix}.png"
    return save_forklift_timeline_plot(result, path, shift_start_hhmm=scenario.shift_start_hhmm, title=title)


def _render_sidebar(scenario):
    st.sidebar.header("Параметры сценария")

    scenario.order_shields_qty = st.sidebar.slider("План отгрузки (щитов)", 20, 160, int(scenario.order_shields_qty), step=2)
    scenario.shift_duration_hours = st.sidebar.slider("Длительность смены, ч", 6.0, 16.0, float(scenario.shift_duration_hours), step=0.5)

    st.sidebar.subheader("Начальные остатки")
    scenario.initial_tubes_at_c1 = st.sidebar.slider("Труб в C1", 0, 80, int(scenario.initial_tubes_at_c1))
    scenario.initial_shields_waiting_c2 = st.sidebar.slider("Щитов в C2", 0, 40, int(scenario.initial_shields_waiting_c2))
    scenario.initial_shields_waiting_c3 = st.sidebar.slider("Щитов в C3", 0, 40, int(scenario.initial_shields_waiting_c3))
    scenario.initial_finished_waiting_c4 = st.sidebar.slider("Готовых в C4", 0, 40, int(scenario.initial_finished_waiting_c4))

    st.sidebar.subheader("Времена операций, мин")
    scenario.handling.tube_load_min = st.sidebar.slider("Погрузка труб", 1.0, 15.0, float(scenario.handling.tube_load_min), step=0.5)
    scenario.handling.tube_unload_min = st.sidebar.slider("Выгрузка труб", 1.0, 15.0, float(scenario.handling.tube_unload_min), step=0.5)
    scenario.handling.shield_load_min = st.sidebar.slider("Погрузка щитов", 1.0, 15.0, float(scenario.handling.shield_load_min), step=0.5)
    scenario.handling.shield_unload_min = st.sidebar.slider("Выгрузка щитов", 1.0, 15.0, float(scenario.handling.shield_unload_min), step=0.5)
    scenario.handling.finished_load_min = st.sidebar.slider("Погрузка готовой продукции", 1.0, 15.0, float(scenario.handling.finished_load_min), step=0.5)
    scenario.handling.finished_unload_min = st.sidebar.slider("Выгрузка готовой продукции", 1.0, 15.0, float(scenario.handling.finished_unload_min), step=0.5)

    st.sidebar.subheader("Время перемещения между цехами, мин")
    t_sc1 = st.sidebar.slider("S -> C1", 0.2, 10.0, float(scenario.travel_time_overrides_min[("S", "C1")]), step=0.1)
    t_c1c2 = st.sidebar.slider("C1 -> C2", 0.2, 10.0, float(scenario.travel_time_overrides_min[("C1", "C2")]), step=0.1)
    t_c2c3 = st.sidebar.slider("C2 -> C3", 0.2, 10.0, float(scenario.travel_time_overrides_min[("C2", "C3")]), step=0.1)
    t_c3c4 = st.sidebar.slider("C3 -> C4", 0.2, 10.0, float(scenario.travel_time_overrides_min[("C3", "C4")]), step=0.1)
    t_c4p = st.sidebar.slider("C4 -> P", 0.2, 10.0, float(scenario.travel_time_overrides_min[("C4", "P")]), step=0.1)

    _set_travel_bidirectional(scenario, "S", "C1", t_sc1)
    _set_travel_bidirectional(scenario, "C1", "C2", t_c1c2)
    _set_travel_bidirectional(scenario, "C2", "C3", t_c2c3)
    _set_travel_bidirectional(scenario, "C3", "C4", t_c3c4)
    _set_travel_bidirectional(scenario, "C4", "P", t_c4p)

    st.sidebar.subheader("Производительность цехов, щитов/час")
    scenario.production.c1_per_hour = st.sidebar.slider("C1", 2.0, 16.0, float(scenario.production.c1_per_hour), step=0.5)
    scenario.production.c2_per_hour = st.sidebar.slider("C2", 2.0, 20.0, float(scenario.production.c2_per_hour), step=0.5)
    scenario.production.c3_per_hour = st.sidebar.slider("C3 (узкое место)", 2.0, 16.0, float(scenario.production.c3_per_hour), step=0.5)
    scenario.production.c4_per_hour = st.sidebar.slider("C4", 2.0, 20.0, float(scenario.production.c4_per_hour), step=0.5)

    st.sidebar.subheader("Веса целевой функции")
    scenario.objective.underproduction_penalty = st.sidebar.number_input("Штраф за недовыпуск", min_value=1000.0, max_value=100000.0, value=float(scenario.objective.underproduction_penalty), step=500.0)
    scenario.objective.makespan_weight = st.sidebar.number_input("Вес общего времени", min_value=0.0, max_value=100.0, value=float(scenario.objective.makespan_weight), step=0.5)
    scenario.objective.c3_starvation_weight = st.sidebar.number_input("Вес простоя C3", min_value=0.0, max_value=200.0, value=float(scenario.objective.c3_starvation_weight), step=1.0)
    scenario.objective.forklift_idle_weight = st.sidebar.number_input("Вес штрафуемого простоя погрузчиков", min_value=0.0, max_value=100.0, value=float(scenario.objective.forklift_idle_weight), step=0.5)

    st.sidebar.subheader("Параметры отжига")
    scenario.sa.iterations = st.sidebar.slider("Итерации", 20, 1500, int(scenario.sa.iterations), step=10)
    scenario.sa.initial_temperature = st.sidebar.number_input("Начальная температура", min_value=100.0, max_value=100000.0, value=float(scenario.sa.initial_temperature), step=500.0)
    scenario.sa.cooling_rate = st.sidebar.slider("Коэффициент охлаждения", 0.90, 0.999, float(scenario.sa.cooling_rate), step=0.001)
    scenario.sa.min_temperature = st.sidebar.number_input("Минимальная температура", min_value=0.001, max_value=10.0, value=float(scenario.sa.min_temperature), step=0.01)
    scenario.sa.seed = st.sidebar.number_input("Seed", min_value=0, max_value=1000000, value=int(scenario.sa.seed), step=1)

def _draw_summary_cards(base_result, sa_result) -> None:
    c1, c2, c3 = st.columns(3)
    c1.metric("Отгружено (жадная)", f"{base_result.metrics.shipped_qty:.1f}")
    c2.metric("Отгружено (отжиг)", f"{sa_result.metrics.shipped_qty:.1f}", delta=f"{sa_result.metrics.shipped_qty - base_result.metrics.shipped_qty:+.1f}")
    c3.metric("Значение целевой функции (меньше лучше)", f"{sa_result.metrics.objective_value:.2f}", delta=f"{sa_result.metrics.objective_value - base_result.metrics.objective_value:+.2f}")

    d1, d2, d3, d4 = st.columns(4)
    d1.metric("Время (жадная)", format_minutes_hms(base_result.metrics.makespan_min))
    d2.metric("Время (отжиг)", format_minutes_hms(sa_result.metrics.makespan_min))
    d3.metric("Простой C3 (жадная)", format_minutes_hms(base_result.metrics.c3_starvation_min))
    d4.metric("Простой C3 (отжиг)", format_minutes_hms(sa_result.metrics.c3_starvation_min))


def _history_rows(history) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for p in history:
        rows.append(
            {
                "Итерация": str(p.iteration),
                "Температура": f"{p.temperature:.4f}",
                "Текущее значение целевой функции": f"{p.current_objective:.2f}",
                "Лучшее значение целевой функции": f"{p.best_objective:.2f}",
            }
        )
    return rows


def main() -> None:
    st.set_page_config(page_title="Логистика цеха — симулятор", layout="wide")
    st.title("Оптимизация внутризаводской логистики")
    st.caption("Имитация отжига переставляет конкретные рейсы исходного расписания и проверяет каждый вариант симуляцией")

    scenario_name = st.sidebar.selectbox(
        "Сценарий",
        options=["sample_day", "sample_night"],
        index=0,
        format_func={
            "sample_day": "Дневная смена",
            "sample_night": "Ночная смена",
        }.get,
    )
    scenario = deepcopy(load_scenario(scenario_name))

    _render_sidebar(scenario)

    run_clicked = st.sidebar.button("Запустить расчёт", type="primary", use_container_width=True)
    if not run_clicked and "ui_results" not in st.session_state:
        st.info("Настройте параметры слева и нажмите «Запустить расчёт».")
        return

    if run_clicked:
        with st.spinner("Идёт симуляция и оптимизация..."):
            base = run_simulation(scenario=scenario, strategy_name="simple", policy=build_simple_policy())
            base_breakdown = evaluate_objective(base, scenario)

            sa_pack = optimize_with_sa(scenario, seed=scenario.sa.seed)
            sa_best = sa_pack.best_result
            sa_breakdown = evaluate_objective(sa_best, scenario)

            st.session_state["ui_results"] = {
                "scenario": scenario,
                "base": base,
                "base_breakdown": base_breakdown.__dict__,
                "sa": sa_best,
                "sa_breakdown": sa_breakdown.__dict__,
                "sa_history": sa_pack.history,
                "sa_iterations_done": sa_pack.iterations_done,
            }

    data = st.session_state.get("ui_results")
    if not data:
        return

    scenario = data["scenario"]
    base = data["base"]
    sa = data["sa"]
    base_breakdown = data["base_breakdown"]
    sa_breakdown = data["sa_breakdown"]
    sa_history = data["sa_history"]

    st.subheader("Сводка")
    st.write(
        f"Смена: **{scenario.shift_type}**, старт **{scenario.shift_start_hhmm}**, длительность **{scenario.shift_duration_hours:.1f} ч**. "
        f"План: **{scenario.order_shields_qty} щитов**. Итераций отжига: **{data['sa_iterations_done']}**."
    )
    _draw_summary_cards(base, sa)

    tab_summary, tab_delta, tab_routes, tab_trips, tab_timeline, tab_sa = st.tabs(
        ["Метрики", "Дельта", "Маршруты", "Журнал рейсов", "Таймлайн", "Отжиг"]
    )

    with tab_summary:
        left, right = st.columns(2)
        left.markdown("**Жадная стратегия**")
        left.dataframe(_summary_rows(base, base_breakdown), use_container_width=True, hide_index=True)
        right.markdown("**Имитация отжига**")
        right.dataframe(_summary_rows(sa, sa_breakdown), use_container_width=True, hide_index=True)

    with tab_delta:
        st.markdown("**Сравнение стратегий**")
        st.code(delta_table(base, sa), language="text")

    with tab_routes:
        lcol, rcol = st.columns(2)
        lcol.markdown("**Жадная стратегия**")
        lcol.dataframe(_route_rows(base), use_container_width=True, hide_index=True)
        rcol.markdown("**Имитация отжига**")
        rcol.dataframe(_route_rows(sa), use_container_width=True, hide_index=True)

    with tab_trips:
        lcol, rcol = st.columns(2)
        lcol.markdown("**Жадная стратегия**")
        lcol.dataframe(_trip_rows(base, scenario.shift_start_hhmm), use_container_width=True, hide_index=True, height=520)
        rcol.markdown("**Имитация отжига**")
        rcol.dataframe(_trip_rows(sa, scenario.shift_start_hhmm), use_container_width=True, hide_index=True, height=520)

    with tab_timeline:
        st.markdown("**График занятости погрузчиков (Gantt-like)**")
        p1 = _timeline_image(base, scenario, "simple", "Жадная стратегия")
        p2 = _timeline_image(sa, scenario, "sa", "Имитация отжига")
        st.image(str(p1), caption="Жадная стратегия", use_container_width=True)
        st.markdown("<div style='height: 24px'></div>", unsafe_allow_html=True)
        st.image(str(p2), caption="Имитация отжига", use_container_width=True)
        st.caption(
            "Цвет сегмента = маршрут; начало/конец сегмента соответствуют реальному времени рейса "
            "(порожний перегон + погрузка + движение + выгрузка). Маршрут определяется по легенде."
        )

    with tab_sa:
        st.markdown("**Ход оптимизации SA**")
        st.caption(
            "Соседнее решение создаётся обменом двух рейсов, переносом рейса "
            "или разворотом небольшого участка расписания."
        )
        if not sa_history:
            st.info("История SA пуста.")
        else:
            chart_rows = [
                {
                    "Итерация": p.iteration,
                    "Лучшее значение целевой функции": p.best_objective,
                    "Текущее значение целевой функции": p.current_objective,
                }
                for p in sa_history
            ]
            st.line_chart(
                chart_rows,
                x="Итерация",
                y=["Лучшее значение целевой функции", "Текущее значение целевой функции"],
                use_container_width=True,
            )
            with st.expander("Таблица итераций SA"):
                st.dataframe(_history_rows(sa_history), use_container_width=True, hide_index=True, height=380)

    st.markdown("---")
    st.markdown("**Маршруты потока:** " + " → ".join(ROUTE_SEQUENCE))
    end_simple = format_clock_time(base.metrics.makespan_min, scenario.shift_start_hhmm)
    end_sa = format_clock_time(sa.metrics.makespan_min, scenario.shift_start_hhmm)
    st.caption(f"Окончание смены по модели: жадная до {end_simple}, отжиг до {end_sa}.")


if __name__ == "__main__":
    main()

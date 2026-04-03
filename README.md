# Оптимизация внутризаводской логистики (timeline + simulated annealing)

Проект моделирует поток `S -> C1 -> C2 -> C3 -> C4 -> P` с 2 погрузчиками и сравнивает:
- `Простая стратегия` (наивная диспетчеризация)
- `Имитация отжига` (оптимизация порядка маршрутов и партий)

Главная цель отчёта: показать не только итоговый `objective`, но и **как** решение достигается во времени.

## Что теперь есть

1. Явная временная модель рейсов.
Каждый рейс содержит интервалы:
- `start_time`
- `load_start/load_end`
- `travel_start/travel_end`
- `unload_start/unload_end`
- `end_time`

2. Журнал рейсов (`trip log`) по времени.

3. Агрегированная статистика маршрутов (`route stats`) по каждой стратегии.

4. Сравнение стратегий с таблицей дельт.

5. Основной график: Gantt-like таймлайн занятости погрузчиков.

## Где что менять

Все ключевые числа в одном месте:
- [/Users/arsen/forklift-logistics/app/config/constants.py](/Users/arsen/forklift-logistics/app/config/constants.py)

Там настраиваются:
- времена движения/погрузки/выгрузки
- буферы
- производительности цехов
- веса objective
- параметры SA

## Ключевые файлы

- Сценарий и конфиг-модели: [/Users/arsen/forklift-logistics/app/domain/scenario.py](/Users/arsen/forklift-logistics/app/domain/scenario.py)
- Сущности результата и `TripRecord`: [/Users/arsen/forklift-logistics/app/domain/entities.py](/Users/arsen/forklift-logistics/app/domain/entities.py)
- Симулятор timeline: [/Users/arsen/forklift-logistics/app/simulation/simulator.py](/Users/arsen/forklift-logistics/app/simulation/simulator.py)
- Формат отчётов (trip log/route stats/delta): [/Users/arsen/forklift-logistics/app/simulation/metrics.py](/Users/arsen/forklift-logistics/app/simulation/metrics.py)
- Целевая функция: [/Users/arsen/forklift-logistics/app/optimization/objective.py](/Users/arsen/forklift-logistics/app/optimization/objective.py)
- Simulated annealing: [/Users/arsen/forklift-logistics/app/optimization/simulated_annealing.py](/Users/arsen/forklift-logistics/app/optimization/simulated_annealing.py)
- CLI: [/Users/arsen/forklift-logistics/app/interfaces/cli.py](/Users/arsen/forklift-logistics/app/interfaces/cli.py)
- Графики: [/Users/arsen/forklift-logistics/app/interfaces/visualization.py](/Users/arsen/forklift-logistics/app/interfaces/visualization.py)

## Целевая функция

Используется взвешенная сумма:

```text
objective =
    underproduction_penalty * underproduction
  + makespan_weight * makespan
  + c3_starvation_weight * c3_starvation
  + forklift_idle_weight * forklift_idle
  + wip_weight * excessive_wip
  + route_fragmentation_weight * route_fragmentation
  + violation_penalty_weight * violations
```

Важно: `underproduction_penalty` доминирует, поэтому недовыпуск сильно ухудшает решение.

## Быстрый запуск в VS Code

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pytest -q
```

### CLI: сравнение стратегий

```bash
python -m app.interfaces.cli compare --scenario sample_day --iterations 120 --show-delta --show-route-stats --show-trip-log
```

### CLI: с сохранением таймлайнов

```bash
python -m app.interfaces.cli compare --scenario sample_day --iterations 120 --plot --plot-timeline-only
```

### Только простая стратегия

```bash
python -m app.interfaces.cli baseline --scenario sample_day --show-route-stats --show-trip-log
```

### Только отжиг

```bash
python -m app.interfaces.cli sa --scenario sample_day --iterations 120 --show-route-stats --show-trip-log
```

### Desktop (Tkinter)

```bash
python run_desktop.py
```

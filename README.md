# Forklift Logistics Optimization (CLI Only)

Максимально упрощённая версия проекта: весь функционал доступен **только через консоль**.

## Что есть в проекте

- CLI режимы: `baseline`, `sa`, `compare`
- Сравнение простой стратегии и simulated annealing
- Метрики, дельта-таблица, маршрутная статистика
- Подробный журнал рейсов с временными интервалами
- ASCII timeline
- График таймлайна погрузчиков (matplotlib)

## Структура (2 основных файла)

- [app/core.py](/Users/arsen/forklift-logistics/app/core.py)
  - сценарии
  - dataclass-сущности
  - событийная симуляция
  - objective
  - simulated annealing
  - форматирование отчётов
  - построение графика
- [app/interfaces/cli.py](/Users/arsen/forklift-logistics/app/interfaces/cli.py)
  - CLI интерфейс

## Быстрый запуск

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## CLI

### Сравнение стратегий

```bash
python -m app.interfaces.cli compare \
  --scenario sample_day \
  --iterations 120 \
  --seed 42 \
  --show-delta \
  --show-route-stats \
  --show-trip-log
```

### Только baseline

```bash
python -m app.interfaces.cli baseline --scenario sample_day --show-route-stats --show-trip-log
```

### Только simulated annealing

```bash
python -m app.interfaces.cli sa --scenario sample_day --iterations 120 --show-route-stats --show-trip-log
```

### Графики

```bash
python -m app.interfaces.cli compare --scenario sample_day --iterations 120 --plot --plot-timeline-only
```

## Примечание

Проект intentionally сделан компактным и плоским: без "чистой архитектуры" и без desktop-версии.

# Forklift Logistics Optimization

Проект можно запускать через **CLI** и через **интерактивный Streamlit UI**.

## Что есть в проекте

- CLI режимы: `baseline`, `sa`, `compare`
- Сравнение жадной стратегии и simulated annealing
- SA переставляет конкретные рейсы исходного расписания
- Метрики, дельта-таблица, маршрутная статистика
- Подробный журнал рейсов с временными интервалами
- График таймлайна погрузчиков (matplotlib)
- Интерактивный интерфейс для анализа сценария и изменения параметров

## Структура

- [app/core.py](/Users/arsen/forklift-logistics/app/core.py)
  - сценарии
  - dataclass-сущности
  - событийная симуляция
  - расчёт значения целевой функции
  - simulated annealing
  - форматирование отчётов
  - построение графика
- [app/interfaces/cli.py](/Users/arsen/forklift-logistics/app/interfaces/cli.py)
  - CLI интерфейс
- [app/ui.py](/Users/arsen/forklift-logistics/app/ui.py)
  - Streamlit-интерфейс на русском языке

## Быстрый запуск

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Запуск интерактивного интерфейса

```bash
streamlit run app/ui.py
```

В интерфейсе можно:
- менять веса целевой функции;
- менять времена операций и маршрутов;
- менять производительности и стартовые остатки;
- запускать сравнение жадной стратегии и SA;
- смотреть маршрутную статистику, журнал рейсов и таймлайн погрузчиков.

Размер партии не является параметром оптимизации. Погрузчик забирает весь
доступный груз, который помещается по массе, количеству и свободному месту
в принимающем буфере.

Имитация отжига начинает с расписания жадной стратегии. Соседние решения
создаются обменом двух рейсов, переносом рейса в другую позицию или разворотом
небольшого участка расписания. Каждый кандидат полностью прогоняется через
симуляцию, после чего сравнивается значение целевой функции.

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

cd /Users/arsen/forklift-logistics
./run_compare.sh

### Только simulated annealing

```bash
python -m app.interfaces.cli sa --scenario sample_day --iterations 120 --show-route-stats --show-trip-log
```

### Графики

```bash
python -m app.interfaces.cli compare --scenario sample_day --iterations 120 --plot --plot-timeline-only
```

## Примечание

Проект intentionally сделан компактным и плоским: без "чистой архитектуры".  
Desktop-версия удалена, но есть полноценный интерактивный web UI (локально через Streamlit).

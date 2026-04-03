"""Единая точка настройки числовых параметров модели.

Меняйте параметры здесь — и сценарий, симуляция и отчёты обновятся.
"""

from __future__ import annotations

# ----------------------------
# Узлы и маршруты
# ----------------------------
NODES: tuple[str, ...] = ("S", "C1", "C2", "C3", "C4", "P")

# Время движения (минуты) между зонами.
# C3->C4 задано как константа 10 минут по постановке.
ROUTE_TRAVEL_TIME_MIN: dict[tuple[str, str], float] = {
    ("S", "C1"): 6.0,
    ("C1", "C2"): 6.0,
    ("C2", "C3"): 6.0,
    ("C3", "C4"): 10.0,
    ("C4", "P"): 6.0,
}

# Расстояния оставлены как reference (если захотите вернуться к расчёту через скорость).
ROUTE_DISTANCES_M: dict[tuple[str, str], float] = {
    ("S", "C1"): 120.0,
    ("C1", "C2"): 100.0,
    ("C2", "C3"): 90.0,
    ("C4", "P"): 50.0,
}

# ----------------------------
# Погрузчики
# ----------------------------
FORKLIFT_COUNT = 2
FORKLIFT_SPEED_KMH = 15.0
FORKLIFT_MAX_WEIGHT_KG = 1700.0
FORKLIFT_MAX_SHIELDS_PER_TRIP = 10
FORKLIFT_MAX_TUBES_PER_TRIP = 14
FORKLIFT_MAX_TRIPS_PER_HOUR = 4

# ----------------------------
# Погрузка/разгрузка (мин)
# ----------------------------
# Сделано чуть медленнее, чтобы влияние расписания было заметнее.
TUBE_LOAD_MIN = 5.0
TUBE_UNLOAD_MIN = 4.0
SHIELD_LOAD_MIN = 5.0
SHIELD_UNLOAD_MIN = 4.0
FINISHED_LOAD_MIN = 5.0
FINISHED_UNLOAD_MIN = 4.0

# ----------------------------
# Производительность цехов (шт/час)
# ----------------------------
C1_DAY_PER_HOUR = 8.0
C1_NIGHT_PER_HOUR = 4.0
C2_PER_HOUR = 12.0
C3_PER_HOUR = 8.0
C4_PER_HOUR = 12.0

# ----------------------------
# Материал
# ----------------------------
TUBE_UNIT_WEIGHT_KG = 120.0
SHIELD_UNIT_WEIGHT_KG = 160.0
PIPES_6800_PER_SHIELD = 1.0
PIPES_6200_PER_SHIELD = 1.0

# ----------------------------
# Целевая функция
# ----------------------------
# Недовыпуск доминирует: 1 щит недовыпуска должен стоить
# значительно больше любых вторичных улучшений.
UNDERPRODUCTION_PENALTY = 15000.0
W_MAKESPAN = 1.0
W_C3_STARVATION = 25.0
W_FORKLIFT_IDLE = 4.0
W_WIP = 6.0
W_ROUTE_FRAGMENTATION = 2.0
W_VIOLATION = 100000.0

# ----------------------------
# Имитация отжига
# ----------------------------
SA_ITERATIONS = 240
SA_INITIAL_TEMPERATURE = 90.0
SA_COOLING_RATE = 0.99
SA_MIN_TEMPERATURE = 0.1
SA_SEED = 42

# ----------------------------
# Партии по умолчанию
# ----------------------------
TUBES_PER_TRIP_DEFAULT = 10
SHIELDS_PER_TRIP_DEFAULT = 6
FINISHED_PER_TRIP_DEFAULT = 6

# ----------------------------
# Буферы (демо-настройка: более конфликтная)
# ----------------------------
C1_TUBE_INPUT_CAPACITY = 30
C1_OUTPUT_CAPACITY = 16
C2_INPUT_CAPACITY = 18
C2_OUTPUT_CAPACITY = 16
C3_INPUT_CAPACITY = 10
C3_OUTPUT_CAPACITY = 8
C4_INPUT_CAPACITY = 12
C4_OUTPUT_CAPACITY = 10
WIP_TARGET_UNITS = 20

# ----------------------------
# Day/Night сценарии
# ----------------------------
DAY_SHIFT_START_HHMM = "08:00"
NIGHT_SHIFT_START_HHMM = "20:00"

DAY_SHIFT_HOURS = 11.0
NIGHT_SHIFT_HOURS = 11.0
DAY_ORDER_SHIELDS = 88
NIGHT_ORDER_SHIELDS = 44

# Начальные остатки (специально неидеальные для демонстрации диспетчеризации).
DAY_INITIAL_TUBES_C1 = 8
DAY_INITIAL_WAITING_C2 = 2
DAY_INITIAL_WAITING_C3 = 0
DAY_INITIAL_WAITING_C4 = 0

NIGHT_INITIAL_TUBES_C1 = 6
NIGHT_INITIAL_WAITING_C2 = 1
NIGHT_INITIAL_WAITING_C3 = 0
NIGHT_INITIAL_WAITING_C4 = 0

MAX_OVERTIME_MIN = 240.0
DEFAULT_RANDOM_SEED = 42

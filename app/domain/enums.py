"""Минимальные перечисления модели."""

from __future__ import annotations

from enum import Enum


class ShiftType(str, Enum):
    DAY = "day"
    NIGHT = "night"

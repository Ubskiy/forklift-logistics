#!/usr/bin/env sh
set -eu

PROJECT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
VENV_PY="$PROJECT_DIR/.venv/bin/python"

if [ ! -x "$VENV_PY" ]; then
  echo "Ошибка: не найден $VENV_PY"
  echo "Создай venv и установи зависимости:"
  echo "  python3 -m venv .venv"
  echo "  . .venv/bin/activate && pip install -r requirements.txt"
  exit 1
fi

exec "$VENV_PY" -m app.interfaces.cli compare --scenario sample_day --iterations 120 --plot --plot-timeline-only "$@"

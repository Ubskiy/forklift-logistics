#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

if [ ! -x ".venv/bin/python" ]; then
  echo "Не найдено виртуальное окружение .venv. Создайте его и установите зависимости."
  exit 1
fi

exec .venv/bin/python -m uvicorn app.api:app --host 0.0.0.0 --port "${PORT:-8000}"

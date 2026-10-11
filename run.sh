#!/usr/bin/env bash
# Запуск бота одной командой:  ./run.sh
set -e
cd "$(dirname "$0")"

if [ ! -d .venv ]; then
  echo "Создаю виртуальное окружение…"
  python3 -m venv .venv
fi

./.venv/bin/pip install -q -r requirements.txt
exec ./.venv/bin/python bot.py

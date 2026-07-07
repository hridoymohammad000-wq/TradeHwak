#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"
PORT="${PORT:-${APP_PORT:-8000}}"
PYTHON_BIN="${PYTHON_BIN:-python3}"

if [ -x ".venv/bin/python3" ]; then
  PYTHON_BIN=".venv/bin/python3"
fi

exec "$PYTHON_BIN" -m uvicorn app.main:app --host 0.0.0.0 --port "$PORT"

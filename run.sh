#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

if [ -f .env ]; then
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
fi

alembic upgrade head
python -m app.bootstrap

PORT="${PORT:-8765}"
exec uvicorn app.main:app --host 0.0.0.0 --port "$PORT" --reload

#!/usr/bin/env bash
set -euo pipefail

if [[ "${LIVE_TRADING_ENABLED:-false}" != "false" ]]; then
  echo "Refusing deployment: LIVE_TRADING_ENABLED must be false" >&2
  exit 1
fi

if [[ "${BROKER_MODE:-FAKE}" != "FAKE" ]]; then
  echo "Refusing deterministic development deployment: BROKER_MODE must be FAKE" >&2
  exit 1
fi

if [[ -z "${DATABASE_URL:-}" ]]; then
  echo "Refusing deployment: DATABASE_URL is required" >&2
  exit 1
fi

alembic upgrade head
alembic current

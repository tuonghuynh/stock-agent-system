#!/usr/bin/env bash
set -euo pipefail

if [[ -z "${DATABASE_URL:-}" ]]; then
  echo "DATABASE_URL is required" >&2
  exit 1
fi

alembic upgrade head
current="$(alembic current)"
heads="$(alembic heads)"
printf 'current=%s\nheads=%s\n' "$current" "$heads"

if [[ -z "$current" || -z "$heads" ]]; then
  echo "Unable to verify Alembic revision" >&2
  exit 1
fi

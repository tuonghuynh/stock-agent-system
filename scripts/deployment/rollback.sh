#!/usr/bin/env bash
set -euo pipefail

usage() {
  echo "usage: rollback.sh <service-id> <previous-deploy-id>" >&2
}

if [[ $# -ne 2 ]]; then
  usage
  exit 2
fi

service_id="$1"
deploy_id="$2"
if [[ -z "${RENDER_API_KEY:-}" ]]; then
  echo "RENDER_API_KEY is required" >&2
  exit 1
fi

if [[ "${CONFIRM_RENDER_ROLLBACK:-}" != "$deploy_id" ]]; then
  echo "DRY RUN: would roll service $service_id back to deploy $deploy_id" >&2
  echo "Set CONFIRM_RENDER_ROLLBACK=$deploy_id to execute." >&2
  exit 3
fi

# Render rollback restores application code only. Database downgrade commands are absent.
curl --fail --silent --show-error \
  --request POST \
  --header "Authorization: Bearer ${RENDER_API_KEY}" \
  --header "Content-Type: application/json" \
  --data "{\"deployId\":\"${deploy_id}\"}" \
  "https://api.render.com/v1/services/${service_id}/rollback"

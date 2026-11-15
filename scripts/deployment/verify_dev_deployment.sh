#!/usr/bin/env bash
set -euo pipefail

python scripts/deployment/post_deploy_smoke.py "$@"
python scripts/deployment/alpaca_readonly_smoke.py

# Render development deployment

This runbook deploys the paper-only development service defined by `render.yaml`. It does not
authorize a production deployment or live brokerage access.

## Local candidate gate

From a clean committed tree, record the full SHA and release version, then run:

```bash
UV_CACHE_DIR=/private/tmp/stock-agent-uv-cache uv sync --frozen
uv run pytest
uv run ruff check .
uv run mypy src
docker build --build-arg GIT_SHA="$(git rev-parse HEAD)" \
  --build-arg RELEASE_VERSION=release-v1 \
  --label "org.opencontainers.image.revision=$(git rev-parse HEAD)" .
```

Docker is unavailable in some local environments. In that case, the static deployment tests may
pass, but AT-037 remains unverified until an actual image build reports both OCI labels.

## Blueprint and secrets

Create or sync the Render Blueprint on the development branch only. The Blueprint fixes
`BROKER_MODE=FAKE` and `LIVE_TRADING_ENABLED=false`. Supply `DEV_TEST_TOKEN`, model credentials,
optional Alpaca paper credentials, and Render API/deploy credentials only through Render or local
environment secrets. Never put values in this repository.

Configure the model provider with `MODEL_PROVIDER=openai` and store the OpenAI project key only in
the `OPENAI_API_KEY` secret. Do not configure or retain a `MODEL_API_KEY` alias.

The paid development web plan runs `scripts/deployment/predeploy.sh` before starting the new
service. That script rejects non-fake or live configuration and applies `alembic upgrade head`.
Render sends traffic only after `/health/ready` succeeds.

## Post-deploy validation

```bash
export DEV_BASE_URL=https://stock-agent-system-dev.onrender.com
export EXPECTED_GIT_SHA=<full-validated-sha>
export DEV_TEST_TOKEN=<secret>
scripts/deployment/verify_dev_deployment.sh
```

The version response must identify the exact expected commit. The optional Alpaca smoke performs
GET requests against the canonical paper endpoint only and never creates an order.

## Rollback test

Identify the previous known-good Render deploy ID. First run the rollback script without the
confirmation variable and verify the dry-run target. Then execute:

```bash
export RENDER_API_KEY=<secret>
export CONFIRM_RENDER_ROLLBACK=<previous-deploy-id>
scripts/deployment/rollback.sh <service-id> <previous-deploy-id>
```

Do not run an Alembic downgrade. The previous release must tolerate the forward-compatible schema.
After rollback, rerun health and version checks, then redeploy the candidate and repeat the critical
smoke checks. Record build ID/digest, deployment IDs, migration result, timestamps, test reports,
rollback, and candidate redeploy evidence in `PROGRESS.md`.

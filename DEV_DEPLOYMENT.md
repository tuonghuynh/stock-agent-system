# Development Deployment and Completion Gate

## Decision

The mandatory remote development target is **Render**, using one Docker-based Python/FastAPI web service and one Render PostgreSQL database. The environment is paper-only; live trading must remain disabled at configuration and code levels.

The same architecture can later move elsewhere, but the MVP is not complete until the Render development deployment and remote integration gate pass.

## Required repository assets

Codex must implement:

```text
Dockerfile
.dockerignore
render.yaml
scripts/verify-dev-deployment.sh
src/test/.../remote-integration/**
```

The Docker image must be built from a committed tree and labeled with:

```text
org.opencontainers.image.revision=<full git SHA>
org.opencontainers.image.version=<release manifest version>
```

The application exposes authenticated operational endpoints:

```text
/health/live
/health/ready
/api/version
```

`/api/version` returns Git commit, release manifest, policy version and workflow version. It must not return secrets, account identifiers or credentials.

## Render Blueprint expectations

`render.yaml` defines:

- a Docker web service using the repository `Dockerfile`;
- a Render PostgreSQL database;
- a health-check path using readiness;
- one instance for the MVP;
- deployment only after CI checks pass;
- graceful shutdown sufficient for in-flight checkpointing;
- non-secret configuration values committed in the Blueprint;
- every secret declared with `sync: false` or provided through a Render environment group;
- `LIVE_TRADING_ENABLED=false` and paper-only broker endpoint enforcement;
- `BROKER_MODE=FAKE` for the deterministic remote integration gate;
- an optional separate Alpaca paper read-only smoke profile.

Render supports health-check paths, Docker services, secret environment variables and deployment after checks pass. Use the current official Blueprint schema while implementing because provider fields may evolve.

## Required secrets

Never commit values for:

```text
DEV_TEST_TOKEN
MODEL_API_KEY
ALPACA_PAPER_KEY
ALPACA_PAPER_SECRET
RENDER_DEPLOY_HOOK_URL or RENDER_API_KEY
```

Database credentials should come from the Render database binding. Model and Alpaca secrets must never be passed to agents as prompt content or written to traces.

## Migration behavior

Preferred behavior is a Render pre-deploy `alembic upgrade head` command where the selected plan supports it. Otherwise, run Alembic during controlled application startup with one instance and keep readiness false until migration succeeds.

Requirements:

- migration failure prevents readiness;
- no automatic destructive rollback migration;
- migrations are forward-compatible with the previous application release;
- rollback restores application code while retaining the forward database schema;
- clean-database and previous-schema migration tests pass before deployment.

## Deployment workflow

The lead performs these steps against the frozen candidate commit:

1. Confirm the working tree is clean and record the full Git SHA.
2. Run `uv sync --frozen`, `uv run pytest`, `uv run ruff check .`, `uv run mypy src` and all required local acceptance tests.
3. Validate `render.yaml`, Dockerfile and `docker compose config` where applicable.
4. Build the Docker image and verify its revision/version labels.
5. Push the candidate commit to the configured development branch.
6. Trigger or observe the Render deployment for that exact commit.
7. Wait for deployment success and readiness; bounded polling only.
8. Call `/api/version` and verify the deployed SHA and versions match the candidate.
9. Run AT-040 through AT-042 against the remote base URL.
10. Run the Alpaca paper read-only smoke check when credentials are configured.
11. Record deployment evidence in `PROGRESS.md`.
12. Test rollback to the previous known-good deployment.
13. Verify health and version after rollback without reverting the database schema.
14. Redeploy the candidate and repeat readiness plus critical smoke tests.

## Post-deployment integration suite

Use `BROKER_MODE=FAKE` so remote tests remain deterministic. The suite must verify:

- authenticated access and rejection of missing/invalid tokens;
- active release, workflow and policy versions;
- accepted recommendation → risk approval → automatic paper intent → fake order → fill;
- rejected recommendation → rule reasons → no broker side effect;
- duplicate intent creates one order;
- pause blocks new submission but does not cancel or liquidate;
- trace ID links recommendation, checks, intent, order and fill/rejection;
- logs and API responses contain no configured secrets;
- service restart preserves durable run, intent and audit state;
- live broker endpoint or `LIVE_TRADING_ENABLED=true` configuration is rejected.

## Alpaca paper smoke

The deployment gate uses fake execution for determinism. When paper credentials are configured, separately verify:

- account is a paper account;
- base URL is the paper endpoint;
- account, market clock, positions and open orders can be read;
- no live URL or credential is accepted.

Do not place a broker order merely to prove deployment. Full order behavior is covered by the fake-broker lifecycle and Alpaca adapter contract tests. Real paper recommendations may execute later under the normal policy gate.

## Failure and rollback

Any failed migration, health check, version mismatch, integration test, redaction test or live-disable check fails the deployment gate.

On failure:

1. stop further tests that could create side effects;
2. preserve deployment logs and test reports without secrets;
3. restore the previous known-good application deployment when necessary;
4. keep the forward-compatible database schema;
5. create a focused repair task in `TASK_BOARD.yaml`;
6. repeat local validation, deploy and remote validation.

## Completion evidence

The lead records:

- exact Git SHA and release manifest;
- image digest or Render build identifier;
- Render deployment identifier and timestamp;
- migration result;
- readiness and version responses;
- remote test report;
- security/redaction report;
- Alpaca paper read-only result or explicit credential blocker;
- rollback and candidate-redeploy results.

Only after all mandatory evidence is present may the lead mark the project complete.

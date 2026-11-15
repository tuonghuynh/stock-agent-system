# Phased Implementation Plan

Complete phases in order. A phase is complete only when its required tests and evidence are recorded in `PROGRESS.md`.

Parallel execution follows `PARALLEL_EXECUTION.md`. A worker starts only when its dependencies are merged into a green integration branch.

## Phase 0 — Repository and contracts

- Create a Python 3.13 project managed by `uv`, with FastAPI, Pydantic v2 and a locked dependency set.
- Establish Python module/package boundaries from `ARCHITECTURE.md`.
- Add PostgreSQL, SQLAlchemy 2, Alembic, validation, test database fixtures and structured logging.
- Implement canonical DTOs, enums and validation.
- Load and validate `POLICY_V1.yaml`.
- Create initial migrations for policies, runs, evidence, recommendations, risk decisions, intents, orders, fills, reservations and audit events.
- Add release manifest and configuration versioning.

**Exit:** clean build; schema migration test; policy validation test; domain serialization tests.

**Parallelism:** lead-owned and mostly sequential. Canonical DTOs, interfaces, build files and database conventions must be frozen before broad parallel work begins.

## Phase 1 — Execution foundation

- Implement `BrokerAdapter` with fake broker and Alpaca paper adapter.
- Implement account, position, open-order, asset and market-clock reads.
- Implement trade-intent persistence, stable idempotency and client order IDs.
- Implement limit-order submission and state transitions.
- Implement fills, partial fills, cancellation and replacement mapping.
- Implement transactional cash/share reservations.
- Implement reconciliation and pause behavior.
- Add restart and ambiguous-submission recovery.

**Exit:** manual eligible intent completes through fake broker; rejection path creates no broker call; all execution failure cases pass.

## Phase 2 — Deterministic policy and risk

- Implement each risk rule as a named component returning a `RiskCheckResult`.
- Implement exposure, sector, cash, turnover and pending-order calculations.
- Implement earnings blackout, universe and tradability rules.
- Implement freshness and expiration checks.
- Implement automatic pause thresholds without cancellation or liquidation.
- Expose rule-level decision API.

**Exit:** all RSK requirements pass, including concurrent reservation tests; accepted violations equal zero.

## Phase 3 — Data, evidence and baselines

- Implement evidence snapshot and provenance storage.
- Implement deterministic technical calculations.
- Add approved source adapters behind interfaces and deterministic fixtures.
- Add prompt-injection-neutralization boundary.
- Implement rules baseline and report.
- Add point-in-time evaluation cases.

**Exit:** reproducible evidence hash and rules recommendation for a fixed case; future-data leakage test passes.

## Phase 4 — Single-agent baseline

- Implement model gateway abstraction plus deterministic fake model.
- Implement structured-output validation, timeout, budget and one repair attempt.
- Implement single-agent recommendation contract.
- Add trace, token and cost records.
- Confirm model has no broker or policy-write tools.

**Exit:** fixed evidence produces validated recommendation or safe failure; injection and malformed-output tests pass.

## Phase 5 — Bounded multi-agent workflow

- Implement Research, Critic and Portfolio adapters.
- Implement immutable run manifest and fixed DAG.
- Add shared budget accounting and durable checkpoints.
- Run independent critique and record material conflicts.
- Add safe termination and restart behavior.
- Connect eligible recommendation to deterministic risk and automatic paper intent.

**Exit:** both accepted and rejected end-to-end flows pass with complete trace; no free-form delegation exists.

## Phase 6 — Evaluation and operational readiness

- Run rules, single-agent and multi-agent variants on identical cases.
- Produce machine-readable and human-readable comparison reports.
- Add operational health, pause/resume and reconciliation endpoints.
- Add local runbook and Alpaca paper smoke-test instructions.
- Execute the complete `ACCEPTANCE_TESTS.md` matrix.
- Resolve every MUST item or document a genuine external blocker.
- Produce final requirement-to-evidence report.

**Exit:** all local requirements and acceptance tests pass; the exact candidate commit and release manifest are frozen for deployment.

## Phase 7 — Development deployment and remote validation

- Implement `Dockerfile`, `.dockerignore`, `render.yaml` and environment templates without secrets.
- Add authenticated health, readiness and development-test API access.
- Configure the Render development web service and PostgreSQL according to `DEV_DEPLOYMENT.md`.
- Deploy the exact validated commit; do not rebuild from an uncommitted working tree.
- Run Alembic migrations and verify readiness.
- Execute post-deployment integration and security tests against the development URL.
- Run Alpaca paper read-only connectivity check when credentials are available.
- Capture deployment and test evidence in `PROGRESS.md`.
- Exercise rollback to the previous known-good development release and redeploy the candidate if rollback succeeds.
- Produce the final completion report only after the development environment is green.

**Exit:** all `DPL` requirements and deployment acceptance tests pass. Local tests without a successful development deployment do not satisfy the definition of done.

## Dependency restraint

Do not add Kafka, Kubernetes, a vector database, a workflow platform or separate deployment units during these phases. A new infrastructure component requires a failed requirement that cannot reasonably be met by FastAPI, SQLAlchemy, PostgreSQL and database-backed jobs, plus a recorded decision in `DECISIONS.md`.


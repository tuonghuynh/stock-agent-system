# Requirements

`MUST` items are required for completion. `SHOULD` items may be deferred only with a documented reason and no safety impact.

## Policy and user input

- **POL-001 MUST:** Load `POLICY_V1.yaml`, validate it and persist an immutable policy version.
- **POL-002 MUST:** Associate every run, recommendation, risk decision and trade intent with the exact policy version.
- **POL-003 MUST:** Support temporary investment views with effective time, review/expiry time, confidence and affected symbols or sectors.
- **POL-004 MUST:** Prevent agents from changing policies or temporary views.
- **POL-005 MUST:** Grandfather existing positions above a limit: no increase is allowed, while hold or reduction remains possible.

## Data and provenance

- **DAT-001 MUST:** Create an immutable point-in-time `EvidenceSnapshot` for each decision run.
- **DAT-002 MUST:** Store source identifier, publisher/provider, retrieval time, source time, content hash and freshness for evidence.
- **DAT-003 MUST:** Calculate technical indicators deterministically.
- **DAT-004 MUST:** Mark unavailable, stale or conflicting material data explicitly.
- **DAT-005 MUST:** Treat external content as untrusted data and ignore instructions embedded within it.
- **DAT-006 SHOULD:** Prefer primary filings and official company sources for material fundamental claims.

## Agent contracts

- **AGT-001 MUST:** Implement Research, Critic and Portfolio contracts with typed, validated inputs and outputs.
- **AGT-002 MUST:** Every finding includes evidence references, confidence, analysis timestamp, assumptions and missing information.
- **AGT-003 MUST:** Agents receive allowlisted read-only tools and cannot access broker tools, secrets or mutable policy APIs.
- **AGT-004 MUST:** Reject malformed output after one bounded schema-repair attempt.
- **AGT-005 MUST:** Prevent agents from adding symbols, changing the time horizon or changing the run objective.
- **AGT-006 SHOULD:** Support a later Analyst role without changing policy or execution interfaces.

## Coordination

- **COR-001 MUST:** Create an immutable `RunManifest` containing objective, universe, time horizon, versions, budgets and deadlines.
- **COR-002 MUST:** Execute a fixed workflow graph with no agent delegation or free-form looping.
- **COR-003 MUST:** Enforce shared budgets for model calls, tool calls, tokens/cost, deadline, fan-out and retries.
- **COR-004 MUST:** Permit at most one critique pass and one constrained repair/revision pass.
- **COR-005 MUST:** Record conflicts and return `NEEDS_REVIEW` or `WAIT` for unresolved material disagreement.
- **COR-006 MUST:** Persist checkpoints and safely resume or terminate after coordinator restart.
- **COR-007 MUST:** A changed objective creates a new run rather than mutating the existing run.

## Baselines and recommendations

- **REC-001 MUST:** Produce a deterministic quality/growth/valuation/trend/momentum baseline.
- **REC-002 MUST:** Produce a single-agent baseline using the same evidence and policy.
- **REC-003 MUST:** Produce a multi-agent recommendation using the same evidence and policy.
- **REC-004 MUST:** Recommendations are one of `BUY`, `SELL`, `HOLD`, `WAIT`, `NEEDS_REVIEW`.
- **REC-005 MUST:** Recommendations include thesis, bull/base/bear cases, contradicting evidence, invalidation conditions, horizon, confidence and target-position proposal.
- **REC-006 MUST:** A recommendation below confidence 65, with missing material evidence, or with unresolved material conflict cannot create a paper intent.
- **REC-007 MUST:** Recommendations expire at the next regular market close or after 24 hours, whichever occurs first.

## Deterministic policy and risk gate

- **RSK-001 MUST:** Only deterministic code may approve or reject a recommendation for execution.
- **RSK-002 MUST:** Validate symbol allowlist, asset tradability and regular-session policy.
- **RSK-003 MUST:** Validate quote, position, pending-order, account and buying-power freshness.
- **RSK-004 MUST:** Include pending orders and local reservations in all cash, share and exposure calculations.
- **RSK-005 MUST:** Enforce single-stock, ETF, sector, cash, initial-position, staged-addition, daily exposure, order-count and weekly-turnover limits.
- **RSK-006 MUST:** Enforce long-only, no margin, no options, no shorting and no extended-hours execution.
- **RSK-007 MUST:** Reject normal new positions within two trading days before earnings.
- **RSK-008 MUST:** Return rule-level results containing rule ID, pass/fail, observed value, limit and reason.
- **RSK-009 MUST:** No model confidence or text may override a failed rule.
- **RSK-010 MUST:** Use transactionally consistent reservations to prevent concurrent overspending or overselling.

## Execution

- **EXE-001 MUST:** Keep brokerage execution behind an interface inaccessible to agents.
- **EXE-002 MUST:** Support fake broker and Alpaca paper implementations; no live implementation may be enabled.
- **EXE-003 MUST:** Persist a trade intent and stable idempotency key before broker submission.
- **EXE-004 MUST:** Duplicate intents return the existing result and create no additional order.
- **EXE-005 MUST:** Submission timeout creates an `UNKNOWN` outcome and triggers broker reconciliation before retry.
- **EXE-006 MUST:** Track accepted, new, partially filled, filled, pending-cancel, canceled, rejected, expired and replaced states.
- **EXE-007 MUST:** Handle fills arriving during cancellation.
- **EXE-008 MUST:** Reconcile local orders, fills, positions, cash and pending reservations with the broker.
- **EXE-009 MUST:** Pause new submissions when material state cannot be reconciled.
- **EXE-010 MUST:** Paper orders require no human approval after all gates pass.
- **EXE-011 MUST:** Live mode remains hard-disabled and would require exact-order human approval in a future release.

## Reliability

- **REL-001 MUST:** Use bounded timeouts and retries with exponential backoff only for identified transient failures.
- **REL-002 MUST:** Do not retry analytical calls until a desired opinion is produced.
- **REL-003 MUST:** Missing required agent output or market data produces safe `WAIT`, `NEEDS_REVIEW` or rejection without order submission.
- **REL-004 MUST:** Restore durable workflow and execution state after application restart.
- **REL-005 MUST:** Automatic pauses trigger at daily loss 3%, weekly loss 6%, drawdown 10%, repeated system rejection or reconciliation failure.
- **REL-006 MUST:** A pause blocks new orders but continues monitoring and reconciliation.
- **REL-007 MUST:** Cancel-open-orders and liquidate-positions are separate explicit operations; pause performs neither.

## Evaluation

- **EVA-001 MUST:** Run rules, single-agent and multi-agent versions against the same versioned cases.
- **EVA-002 MUST:** Prevent future-data leakage in historical cases.
- **EVA-003 MUST:** Track citation validity, unsupported claims, freshness, conflict detection, calibration, return, drawdown, turnover, latency, model/tool calls and cost.
- **EVA-004 MUST:** Track deterministic risk violations; accepted risk violations must equal zero.
- **EVA-005 MUST:** Include malformed output, prompt injection, stale data, conflicting sources and broker-failure cases.
- **EVA-006 SHOULD:** Produce a machine-readable and human-readable comparison report.

## Observability, audit and security

- **OBS-001 MUST:** Use one trace ID from request through final fill or rejection.
- **OBS-002 MUST:** Record run, data, model, prompt, tool, workflow and policy versions.
- **OBS-003 MUST:** Record rule checks, agent outputs, validation errors, order transitions, fills, latency and estimated cost.
- **OBS-004 MUST:** Redact secrets, tokens, account identifiers and unnecessary personal financial data.
- **SEC-001 MUST:** Enforce least-privilege tool access per role in trusted code.
- **SEC-002 MUST:** Validate all tool parameters and agent handoff schemas.
- **SEC-003 MUST:** Keep paper credentials outside source and isolate them from model processes and prompts.
- **SEC-004 MUST:** Detect and neutralize prompt-injection instructions in retrieved content.
- **SEC-005 MUST:** Treat agent output as untrusted and validate it before any state transition.

## Safe change management

- **CHG-001 MUST:** Version prompts, models, tools, schemas, workflow and policies.
- **CHG-002 MUST:** Store a release manifest for every evaluated run.
- **CHG-003 MUST:** Support evaluation of a candidate release without changing the active release.
- **CHG-004 MUST:** Support rollback to the last known configuration without data migration loss.
- **CHG-005 MUST:** Agents may propose improvements but cannot apply them.

## Development deployment

- **DPL-001 MUST:** Package the application as a reproducible Docker image labeled with the exact Git commit and release manifest version.
- **DPL-002 MUST:** Provide a Render Blueprint for a development web service and PostgreSQL database with live trading disabled.
- **DPL-003 MUST:** Store deployment hooks, API tokens, database credentials, model keys and Alpaca paper credentials only as environment secrets.
- **DPL-004 MUST:** Run Alembic migrations before accepting development traffic; readiness remains false until migrations and critical dependencies succeed.
- **DPL-005 MUST:** Deploy only a commit whose full local verification and required CI checks pass.
- **DPL-006 MUST:** After deployment, run integration tests against the deployed API covering accepted and rejected recommendation paths, fake-broker execution, idempotency, pause behavior, authentication, trace linkage and secret redaction.
- **DPL-007 MUST:** Verify the Alpaca paper adapter with a read-only development smoke check when paper credentials are configured; never contact a live endpoint.
- **DPL-008 MUST:** Record deployed commit, image digest or build ID, deployment ID, migration result, test report and timestamp in `PROGRESS.md`.
- **DPL-009 MUST:** Maintain and test rollback to the previous known-good development deployment without destructive database rollback.
- **DPL-010 MUST:** A failed migration, health check, integration test or security check prevents the task from being marked complete.


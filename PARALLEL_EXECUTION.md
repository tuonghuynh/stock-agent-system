# Parallel Codex Execution Plan

## Operating model

Use one **Lead/Integrator Codex** and at most four concurrent implementation workers. A fifth temporary worker may investigate a failure but must not edit paths owned by an active worker. The lead is the only merge authority.

## Isolated worktrees

Parallel agents may share a filesystem, so every worker uses a separate Git branch and worktree. Two agents must never edit the same checkout.

```text
integration/phase-1
agent/P1-EXEC-001       ../stock-agent-worktrees/P1-EXEC-001
agent/P1-RISK-001       ../stock-agent-worktrees/P1-RISK-001
agent/P1-DATA-001       ../stock-agent-worktrees/P1-DATA-001
agent/P1-OBS-001        ../stock-agent-worktrees/P1-OBS-001
```

The lead creates each worktree from the current validated integration commit and gives the worker its exact absolute path.

## Lead responsibilities

The lead owns:

- Phase 0 bootstrap and contract freeze;
- integration branches and worker worktrees;
- parent build files, shared configuration and dependency versions;
- canonical public DTOs and interfaces;
- Alembic revision ordering and shared schema changes;
- `INTERFACES.md`, `POLICY_V1.yaml`, `DECISIONS.md`, `TASK_BOARD.yaml` and `PROGRESS.md`;
- non-overlapping task assignments;
- merge order, conflicts and independent validation;
- full acceptance suite and completion declaration.

The integration branch must remain buildable. Repair or revert a breaking merge before integrating another worker.

## Worker task contract

Every assignment includes:

```yaml
task_id: P1-EXEC-001
owner: worker-execution
base_commit: <validated integration commit>
contract_version: contracts-v1
branch: agent/P1-EXEC-001
worktree: ../stock-agent-worktrees/P1-EXEC-001
depends_on: [P0-BOOT-001]
requirements: [EXE-001, EXE-003, EXE-004]
acceptance_tests: [AT-016]
owned_paths:
  - src/stock_agent/execution/**
  - tests/execution/**
forbidden_paths:
  - pyproject.toml
  - uv.lock
  - migrations/**
  - PROGRESS.md
  - TASK_BOARD.yaml
verification:
  - uv run pytest tests/execution
completion: Commit a complete idempotent-intent slice and return a handoff.
```

No active tasks may have overlapping owned paths.

## Worker rules

1. Work only in the assigned worktree and branch.
2. Verify the assigned base commit and contract version.
3. Edit only owned paths and do not create duplicate shared interfaces.
4. Return shared changes as contract-change requests.
5. Run focused and relevant integration tests.
6. Commit coherent changes with the task ID in every commit subject.
7. Return a completed `HANDOFF_TEMPLATE.md` with commit SHA and exact results.
8. Stop at the task boundary.

## Contract changes

Shared contracts are frozen during each wave. A change request names affected requirements, explains why existing extension points are insufficient, describes compatibility and migration impact, and lists dependent tasks. The lead rejects it, implements it centrally or creates a dedicated contract task. Workers must not invent incompatible replacements.

## Parallel waves

### Foundation gate — lead

Phase 0 stays mostly sequential. The lead establishes the project, modules, canonical DTOs, broker/model interfaces, policy loader, migration conventions, fixtures and architecture dependency tests. Freeze this as `contracts-v1` before assigning implementation workers.

### Wave 1 — deterministic foundations

| Worker | Scope |
|---|---|
| Execution | Trade-intent state machine, idempotency and fake broker |
| Risk | Policy rules, portfolio calculations and rule results |
| Data | Evidence provenance, technical indicators and fixtures |
| Operations | Audit/tracing, redaction and adversarial fixtures |

Gate: integrate one branch at a time, run module tests after each, then full verification and the fake-broker lifecycle.

### Wave 2 — adapters and recovery

| Worker | Scope |
|---|---|
| Execution | Alpaca paper adapter, reconciliation and cancellation races |
| Risk | Reservation concurrency, pause rules and freshness checks |
| Data | Rules baseline and point-in-time evaluation cases |
| Model | Model gateway, structured output, budgets and repair behavior |

Gate: clean migrations, concurrency, restart, timeout and injection tests.

### Wave 3 — bounded agent workflow

| Worker | Scope |
|---|---|
| Coordinator | Fixed DAG, shared budgets, checkpoints and recovery |
| Research | Research Agent adapter |
| Critic | Independent Critic adapter |
| Portfolio | Portfolio Agent adapter |

Gate: validate dependency rules and permissions, then run accepted, rejected, `WAIT` and `NEEDS_REVIEW` paths.

### Wave 4 — system validation

| Worker | Scope |
|---|---|
| End-to-end | Accepted and rejected recommendation-to-fill paths |
| Reliability | Broker failures, restarts, duplicates, partial fills and cancellation |
| Evaluation | Rules/single/multi-agent comparison and metrics |
| Security | Injection, least privilege, trace completeness and redaction |

Gate: the lead runs all local acceptance tests and freezes the candidate commit. This is not yet project completion.

### Wave 5 — development deployment

| Worker | Scope |
|---|---|
| Deployment | Docker, Render Blueprint, environment validation and deployment automation |
| Remote tests | Post-deployment API, idempotency, pause and restart tests |
| Security | Deployed authentication, secret redaction and live-trading-disable checks |
| Lead | Deployment, migration evidence, rollback and final completion report |

Final gate: all local tests plus AT-037 through AT-043 pass against the exact deployed commit. The lead must not mark the project complete before this gate.

## Integration procedure

For every handoff:

1. Verify task ownership, base commit and changed paths.
2. Review commits and contract compatibility.
3. Update the worker branch to the current integration branch when required.
4. Rerun focused tests.
5. Integrate exactly one worker.
6. Run affected module and contract tests.
7. After two or three merges, run the complete fake-broker path.
8. Run `uv run pytest`, `uv run ruff check .` and `uv run mypy src` before declaring the wave green.
9. Update `TASK_BOARD.yaml` and `PROGRESS.md`.
10. Start the next wave only from the validated integration commit.

Do not integrate skipped required tests, new flaky tests, unresolved risk failures, unauthorized paths or live-trading capability.

## Shared-file conflict prevention

- The lead allocates Alembic revision identifiers and edits shared migrations.
- Workers describe schema needs in their handoff.
- Only the lead edits the parent build and shared configuration during a wave.
- Generated files have one owner.
- Workers never merge one another's branches.

## Stalls and recovery

- Every task has bounded time, tool and retry budgets.
- A stalled worker commits a safe buildable checkpoint when possible and reports the blocker.
- The lead marks it `BLOCKED`, then splits, reassigns or supersedes it.
- Never allow two agents to unknowingly continue the same task.
- Abandoned branches remain unmerged.
- Restore the last green integration state before issuing a repair task.
- Replacement workers resume from commits and structured handoffs, not chat memory.

## Parallelism metrics

Track elapsed time, model/tool cost, requirements completed, merge conflicts, integration failures, defects, and rework from contract changes. Reduce the worker count when coordination cost exceeds saved time.


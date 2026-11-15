# Implementation Progress Ledger

Codex must update this file after each completed increment. Do not mark an item complete without test or validation evidence.

## Current status

- Current phase: Wave 2 validated; Wave 3 ready
- Active requirement IDs: COR-002..COR-007, AGT-001, AGT-002, AGT-005, REC-003..REC-007
- Last successful full build: Wave 2 integration verification passed 2026-11-14 (92 tests, Ruff and strict mypy green)
- Blocking issues: None
- Integration branch: `codex/python-phase0`
- Frozen contract version: `contracts-v1-python`
- Active parallel wave: Wave 3 — research, critic and portfolio role slices active

## Phase checklist

- [x] Phase 0 — Repository and contracts
- [ ] Phase 1 — Execution foundation
- [ ] Phase 2 — Deterministic policy and risk
- [ ] Phase 3 — Data, evidence and baselines
- [ ] Phase 4 — Single-agent baseline
- [ ] Phase 5 — Bounded multi-agent workflow
- [ ] Phase 6 — Evaluation and operational readiness
- [ ] Phase 7 — Development deployment and remote validation

## Requirement evidence

| Requirement IDs | Implementation | Tests/validation | Status |
|---|---|---|---|
| POL-001 | Strict Policy v1 loader plus immutable, idempotent version store | `test_policy.py`, `test_policy_store.py` / AT-001 | Validated |
| POL-002, COR-001 | Frozen canonical Pydantic contracts carrying exact versions | `test_domain_models.py` / AT-002 | Validated |
| CHG-001 | Versioned release, workflow, schema, prompts and tools | `test_release.py` | Validated |
| SEC-001 foundation | Package boundary prohibits agent access to execution | `test_architecture.py` | Validated |
| DPL-004 foundation | Alembic migration compiles for PostgreSQL | `test_migrations.py` | Validated locally; live PostgreSQL application remains deployment-gate work |
| RSK-001, RSK-002, RSK-005, RSK-008, RSK-009 | Deterministic 14-rule paper-only risk engine with rule-level evidence, exposure limits, grandfathering and earnings blackout | `tests/risk/test_engine.py` / AT-011, AT-012, AT-015 | Validated |
| EXE-001, EXE-003, EXE-004 | Paper-only broker boundary, explicit state machine, canonical idempotency, persist-before-submit and atomic duplicate suppression | `tests/execution/test_execution.py` / AT-016 | Validated |
| DAT-001, DAT-002, DAT-003, DAT-004 | Immutable canonical evidence snapshots, provenance/freshness states, point-in-time boundaries and Decimal SMA/EMA/Wilder RSI | `tests/evidence/` / AT-029 boundary | Validated |
| OBS-001, OBS-002, OBS-004, SEC-004 | Append-only audit, linked trace/version context, recursive redaction and frozen hostile-content authority | `tests/observability/` / AT-003, AT-027, AT-028 | Validated |
| RSK-003, RSK-004, RSK-010, REL-005, REL-006 | Atomic cash/share reservations, material-input freshness, pending exposure and latched safety pause | `tests/risk/test_reservations.py`, `test_freshness_pause_authorization.py` / AT-010, AT-013, AT-014, AT-023 | Validated |
| EXE-002, EXE-005, EXE-006, EXE-007, EXE-008, EXE-009 | Paper-only Alpaca boundary, ambiguity/restart recovery, fills, cancel races, reconciliation and deterministic pricing | `tests/execution/test_recovery_and_alpaca.py` / AT-017..AT-022, AT-036 | Validated |
| REC-001, EVA-001, EVA-002 | Deterministic five-factor rules baseline and identical-snapshot three-variant comparison boundary | `tests/baseline/`, `tests/evaluation/` / AT-029, AT-030 | Validated |
| AGT-002, AGT-003, AGT-004, REC-002 | Bounded structured model gateway with strict schemas, read-only tools, one repair, budgets and safe WAIT | `tests/model_gateway/test_gateway.py` / AT-004, AT-005, AT-025, AT-026 | Validated |
| COR-005, REC-006 | Independent deterministic critic with material objections, bounded dispositions and no execution authority | `tests/agents/critic/test_critic.py` / AT-008 | Validated |

## Integrated worker handoffs

Only the lead updates this table after independently validating and integrating a worker commit.

| Task ID | Agent | Commit | Requirements/tests | Validation | Status |
|---|---|---|---|---|---|
| P1-RISK-001 | worker-risk | `f148085` | RSK-001, RSK-002, RSK-005, RSK-008, RSK-009 / AT-011, AT-012, AT-015 | 9 focused and 20 full tests; Ruff and strict mypy green | Validated |
| P1-EXEC-001 | worker-execution | `d9985c5` | EXE-001, EXE-003, EXE-004 / AT-016 | 6 focused and 26 full tests; Ruff and strict mypy green | Validated |
| P1-DATA-001 | worker-data | `c0fa5c1` | DAT-001, DAT-002, DAT-003, DAT-004 / AT-029 boundary | 8 focused and 34 full tests; Ruff and strict mypy green | Validated |
| P1-OBS-001 | worker-observability | `8502e4e` | OBS-001, OBS-002, OBS-004, SEC-004 / AT-003, AT-027, AT-028 | 8 focused and 42 full tests; Ruff and strict mypy green | Validated |
| P2-RISK-001 | worker-risk-concurrency | `1c749ce` | RSK-003, RSK-004, RSK-010, REL-005, REL-006 / AT-010, AT-013, AT-014, AT-023 | 22 focused and 55 full tests; Ruff and strict mypy green | Validated |
| P2-EXEC-001 | worker-execution-recovery | `a5127ee` | EXE-002, EXE-005..EXE-009 / AT-017..AT-022, AT-036 | 23 focused and 72 full tests; Ruff and strict mypy green | Validated |
| P2-BASE-001 | worker-baseline | `97777d6` | REC-001, EVA-001, EVA-002 / AT-029, AT-030 | 8 focused and 80 full tests; Ruff and strict mypy green | Validated |
| P2-MODEL-001 | worker-model-gateway | `eb01d58` | AGT-002, AGT-003, AGT-004, REC-002 / AT-004, AT-005, AT-025, AT-026 | 12 focused and 92 full tests; Ruff and strict mypy green | Validated |
| P3-CRITIC-001 | worker-critic-agent | `4bb15b9` | COR-005, REC-006 / AT-008 | 8 focused and 100 full tests; Ruff and strict mypy green | Validated |

## Development deployment evidence

| Field | Value |
|---|---|
| Environment | Render development |
| Git commit | Not deployed |
| Release manifest | Not deployed |
| Image digest/build ID | Not deployed |
| Deployment ID | Not deployed |
| Migration result | Not run |
| Health/readiness | Not run |
| Remote integration report | Not run |
| Security/redaction report | Not run |
| Alpaca paper read-only smoke | Not run |
| Rollback test | Not run |
| Deployment timestamp | — |

## Acceptance results

| Test ID | Command or test | Result | Evidence/date |
|---|---|---|---|
| AT-001..AT-036 | Not run | Pending | — |

## Commands executed

Record the exact command, result and relevant failure summary. Do not paste secrets or excessive logs.

| Date/time | Command | Result |
|---|---|---|
| 2026-11-14 | `uv lock --check` | PASS — 56 packages locked |
| 2026-11-14 | `pytest` | PASS — 11 tests, 0 failures |
| 2026-11-14 | `ruff check .` | PASS |
| 2026-11-14 | `mypy src` | PASS — 21 source files, strict mode |
| 2026-11-14 | `pytest tests/risk` | PASS — 9 tests, 0 failures |
| 2026-11-14 | `ruff check src/stock_agent/risk tests/risk` | PASS |
| 2026-11-14 | `mypy src` | PASS — 23 source files, strict mode |
| 2026-11-14 | `pytest` after P1-RISK-001 integration | PASS — 20 tests, 0 failures |
| 2026-11-14 | `pytest tests/execution` | PASS — 6 tests, 0 failures |
| 2026-11-14 | `ruff check src/stock_agent/execution tests/execution` | PASS |
| 2026-11-14 | `mypy src` after P1-EXEC-001 integration | PASS — 29 source files, strict mode |
| 2026-11-14 | `pytest` after P1-EXEC-001 integration | PASS — 26 tests, 0 failures |
| 2026-11-14 | `pytest tests/evidence` | PASS — 8 tests, 0 failures |
| 2026-11-14 | `ruff check src/stock_agent/evidence tests/evidence` | PASS |
| 2026-11-14 | `mypy src` after P1-DATA-001 integration | PASS — 31 source files, strict mode |
| 2026-11-14 | `pytest` after P1-DATA-001 integration | PASS — 34 tests, 0 failures |
| 2026-11-14 | `pytest tests/observability` | PASS — 8 tests, 0 failures |
| 2026-11-14 | `ruff check .` after P1-OBS-001 integration | PASS |
| 2026-11-14 | `mypy src` after P1-OBS-001 integration | PASS — 35 source files, strict mode |
| 2026-11-14 | `pytest` after P1-OBS-001 integration | PASS — 42 tests, 0 failures |
| 2026-11-14 | `uv lock --check` and Wave 1 integration gate | PASS — lock valid; 27 cross-module gate tests passed |
| 2026-11-14 | `pytest tests/risk` after P2-RISK-001 | PASS — 22 tests, 0 failures |
| 2026-11-14 | `ruff check src/stock_agent/risk tests/risk` | PASS |
| 2026-11-14 | `mypy src` after P2-RISK-001 | PASS — 39 source files, strict mode |
| 2026-11-14 | `pytest` after P2-RISK-001 | PASS — 55 tests, 0 failures |
| 2026-11-14 | `pytest tests/execution` after P2-EXEC-001 | PASS — 23 tests, 0 failures |
| 2026-11-14 | `ruff check src/stock_agent/execution tests/execution` | PASS |
| 2026-11-14 | `mypy src` after P2-EXEC-001 | PASS — 42 source files, strict mode |
| 2026-11-14 | `pytest` after P2-EXEC-001 | PASS — 72 tests, 0 failures |
| 2026-11-14 | `pytest tests/baseline tests/evaluation` | PASS — 8 tests, 0 failures |
| 2026-11-14 | `ruff check src tests` after P2-BASE-001 | PASS |
| 2026-11-14 | `mypy src` after P2-BASE-001 | PASS — 47 source files, strict mode |
| 2026-11-14 | `pytest` after P2-BASE-001 | PASS — 80 tests, 0 failures |
| 2026-11-14 | `pytest tests/model_gateway` | PASS — 12 tests, 0 failures |
| 2026-11-14 | `ruff check .` after P2-MODEL-001 | PASS |
| 2026-11-14 | `mypy src` after P2-MODEL-001 | PASS — 51 source files, strict mode |
| 2026-11-14 | `pytest` after P2-MODEL-001 | PASS — 92 tests, 0 failures |
| 2026-11-14 | `uv lock --check` after Wave 2 | PASS — 56 packages resolved |
| 2026-11-14 | `pytest tests/agents/critic` | PASS — 8 tests, 0 failures |
| 2026-11-14 | `ruff check src/stock_agent/agents/critic tests/agents/critic` | PASS |
| 2026-11-14 | `mypy src` after P3-CRITIC-001 | PASS — 54 source files, strict mode |
| 2026-11-14 | `pytest` after P3-CRITIC-001 | PASS — 100 tests, 0 failures |

## Decisions and deviations

Record any implementation decision not already covered by `DECISIONS.md`, including reason, alternatives and impact. Material scope changes require user input.

None recorded.

## Known limitations

- Docker is not currently available locally. Alembic PostgreSQL SQL generation is validated; applying migrations to a real PostgreSQL service remains required in the broader integration and deployment gates.

## Next action

Integrate and validate the active research, critic and portfolio slices, then dispatch the coordinator from the next green commit.


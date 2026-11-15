# Architecture Decision Log

## D-001 — Python modular monolith first

Use one Python 3.13 FastAPI deployment with strict Pydantic v2 boundary models, SQLAlchemy 2, Alembic and internal package boundaries. This minimizes operational failure modes while preserving future separation.

## D-002 — Deterministic coordinator

Use a fixed workflow DAG and durable checkpoints. Models fill bounded analytical roles but cannot route or delegate work. This prevents loops and silent objective changes. Added complexity: explicit workflow state.

## D-003 — Three initial agents

Use Research, Critic and Portfolio roles. Fold thesis construction into Portfolio initially. A separate Analyst role requires measured evaluation benefit. Added complexity: two extra model calls versus a single-agent baseline.

## D-004 — Separate execution boundary

Broker access belongs only to execution code. Recommendations are proposals and cannot invoke broker tools. This reduces financial and prompt-injection risk. Added complexity: typed intent and reconciliation boundary.

## D-005 — Paper orders need no human approval

Eligible paper recommendations execute automatically after deterministic gates. This exercises the real lifecycle. Live trading remains disabled and future live orders require exact-order approval.

## D-006 — PostgreSQL-backed coordination

Use database claiming, checkpoints, reservations and an outbox-style side-effect record. Do not add Kafka for the MVP. Added complexity: transactional job semantics, offset by simpler operation.

## D-007 — Same evidence for comparisons

Rules, single-agent and multi-agent variants receive the same point-in-time snapshot and policy. This isolates coordination benefit. Added complexity: immutable snapshots and replay tooling.

## D-008 — No self-modification

Prompts, models, tools, schemas, workflow and policies are versioned release artifacts. Agents may propose changes but cannot apply them. Added complexity: release manifest and evaluation promotion.

## D-009 — Safe defaults

Use the limits in `POLICY_V1.yaml`. These are versioned starting assumptions, not permanent financial truths. Update only through a new policy version and evaluation.

## Open decisions

No open decision blocks the MVP. Future decisions include the production model provider, paid market-data provider, hosting target and criteria for limited live trading.


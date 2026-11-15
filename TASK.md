# Task and Definition of Done

## Objective

Build a reliable paper-trading system in which bounded AI agents research and recommend portfolio actions, deterministic services enforce personal policy and risk limits, and a separate execution module submits eligible orders to Alpaca paper trading without human approval.

## Required outcome

The MVP must support this end-to-end lifecycle:

1. Create an immutable decision run with a versioned policy and point-in-time data snapshot.
2. Produce a rules-based baseline recommendation.
3. Produce structured model findings through bounded agent contracts.
4. Coordinate Research, Critic and Portfolio roles without open-ended agent conversation.
5. Validate all outputs and record evidence, confidence, timestamps and sources.
6. Convert an eligible recommendation into a proposed target position.
7. Apply deterministic policy, portfolio and risk checks.
8. Automatically create a paper `TradeIntent` when all gates pass.
9. Submit idempotently through the separate execution boundary.
10. Track order states, partial fills, cancellation and reconciliation.
11. Trace the final fill or rejection back to its data, policy, agents and checks.
12. Evaluate rules, single-agent and multi-agent variants on the same cases.
13. Build an immutable container for the integrated commit and deploy it to the Render development environment.
14. Apply development database migrations and verify health/readiness.
15. Run post-deployment integration, security and recovery smoke tests against the deployed API.
16. Record deployment evidence and prove rollback before declaring completion.

## In scope

- Python 3.13 and FastAPI modular monolith
- PostgreSQL, SQLAlchemy 2, Alembic and durable checkpoints
- Alpaca paper-trading adapter plus deterministic fake broker
- U.S. liquid stocks and approved unleveraged ETFs
- Long-only limit orders during regular market hours
- Policy v1 and temporary user views
- Rules baseline, single-agent baseline and three-agent workflow
- Research, Critic and Portfolio agent contracts
- Deterministic coordinator, policy engine, risk engine and execution engine
- API, audit log, traces, metrics and operational pause control
- Historical point-in-time and adversarial evaluation fixtures
- Local development and repeatable test execution
- Docker packaging, Render development deployment and post-deployment integration tests

## Explicitly out of scope

- Live trading
- Options, short selling, margin and crypto
- High-frequency or intraday scalping strategies
- Autonomous policy or prompt modification
- Unbounded agent delegation or free-form group chat
- Multi-region operation
- Kubernetes, Kafka and independently deployed microservices
- Production-grade graphical dashboard; API and minimal operational views are sufficient

## Definition of done

All `MUST` requirements in `REQUIREMENTS.md` and all `Required` cases in `ACCEPTANCE_TESTS.md` pass. The system demonstrates both paths:

- accepted recommendation → automatic paper intent → fake broker order → fill → reconciled position;
- rejected recommendation → explicit rule-level reasons → no broker side effect.

The system must recover safely from process restart and ambiguous broker submission. It must be impossible for any model or retrieved document to access brokerage credentials or bypass deterministic checks.

The task is complete only after the exact validated commit is deployed to the development environment, its migrations and health checks pass, the required remote integration suite passes, and rollback to the previous known-good development release has been tested. Local success alone cannot satisfy the definition of done.


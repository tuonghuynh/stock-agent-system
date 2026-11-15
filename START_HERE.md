# Stock Trading Multi-Agent System — Codex Implementation Packet

This packet is the source of truth for implementing the paper-trading MVP. Copy the entire directory into the root of the implementation repository, keep `AGENTS.md` at repository root, and start Codex with:

> Read `AGENTS.md` and follow it. Implement the complete paper-trading MVP described by this repository. Work phase by phase, test and validate each increment, update `PROGRESS.md`, and continue until every completion criterion in `TASK.md` and `ACCEPTANCE_TESTS.md` passes or a genuine external blocker is recorded.

## Reading order

1. `AGENTS.md` — operating rules and iteration loop
2. `TASK.md` — objective, scope and definition of done
3. `REQUIREMENTS.md` — numbered functional and nonfunctional requirements
4. `ARCHITECTURE.md` — component boundaries, agent contracts and data flows
5. `INTERFACES.md` — canonical domain objects and state machines
6. `POLICY_V1.yaml` — initial investment and execution policy
7. `IMPLEMENTATION_PLAN.md` — phases and ordered backlog
8. `ACCEPTANCE_TESTS.md` — required validation matrix
9. `PARALLEL_EXECUTION.md` — lead/worker workflow, worktrees and integration gates
10. `TASK_BOARD.yaml` — machine-readable assignments and dependencies
11. `HANDOFF_TEMPLATE.md` — required worker completion report
12. `DEV_DEPLOYMENT.md` — mandatory development deployment and post-deploy gate
13. `DECISIONS.md` — settled architectural decisions
14. `PROGRESS.md` — lead-owned implementation ledger

## Governing principle

Models may interpret evidence and propose decisions. Trusted deterministic code controls authorization, workflow state, portfolio calculations, risk limits, approval requirements and brokerage execution.

## Initial operating mode

- U.S. liquid stocks and selected unleveraged ETFs
- Long-only, regular market hours
- Alpaca paper trading
- No human approval for paper orders that pass all gates
- Human approval required for every future live order
- Live trading is outside this MVP

## Parallel implementation

When multiple Codex agents are available, the lead must follow `PARALLEL_EXECUTION.md`. Phase 0 is led centrally to freeze shared contracts. Later work uses at most four implementation workers, each in a separate Git branch and worktree with non-overlapping path ownership. The lead alone integrates changes and declares completion.


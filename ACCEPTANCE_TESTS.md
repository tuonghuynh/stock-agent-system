# Acceptance Test Matrix

All rows marked `Required` must pass. Test IDs should appear in test names or reports.

| ID | Required behavior | Level | Required |
|---|---|---|---|
| AT-001 | Policy v1 loads, validates and is immutable | Integration | Yes |
| AT-002 | Every decision artifact carries exact policy and release versions | Integration | Yes |
| AT-003 | External prompt-injection text cannot change objective, tools or output schema | Adversarial | Yes |
| AT-004 | Research output without evidence or timestamps is rejected | Contract | Yes |
| AT-005 | Malformed model output receives one repair attempt and then fails safely | Integration | Yes |
| AT-006 | Agent cannot add an unrequested symbol or change horizon | Contract | Yes |
| AT-007 | Workflow terminates within model/tool/time budgets | Integration | Yes |
| AT-008 | Unresolved material analyst/critic conflict yields `NEEDS_REVIEW` and no order | End-to-end | Yes |
| AT-009 | Confidence below 65 yields no intent | End-to-end | Yes |
| AT-010 | Missing or stale material data yields no intent | End-to-end | Yes |
| AT-011 | Position over limit cannot be increased | Domain | Yes |
| AT-012 | Grandfathered over-limit position can be reduced | Domain | Yes |
| AT-013 | Pending orders and reservations are included in exposure | Concurrency | Yes |
| AT-014 | Concurrent eligible intents cannot overspend cash | Concurrency | Yes |
| AT-015 | Earnings blackout rejects normal new position | Domain | Yes |
| AT-016 | Same intent submitted twice creates one broker order | Integration | Yes |
| AT-017 | Lost submission response reconciles by client order ID before retry | Failure recovery | Yes |
| AT-018 | Restart during submission recovers without duplicate order | Failure recovery | Yes |
| AT-019 | Partial fill updates position and preserves remaining reservation | Integration | Yes |
| AT-020 | Fill during cancellation is recorded correctly | Failure recovery | Yes |
| AT-021 | Stream loss triggers REST reconciliation | Failure recovery | Yes |
| AT-022 | Material local/broker mismatch pauses new submissions | Failure recovery | Yes |
| AT-023 | Pause neither cancels open orders nor liquidates positions | Domain | Yes |
| AT-024 | Paper eligible recommendation submits without human approval | End-to-end | Yes |
| AT-025 | Live environment configuration is rejected | Security | Yes |
| AT-026 | Agents and model gateway cannot access broker credentials | Security | Yes |
| AT-027 | Logs and traces contain no configured secrets or account identifiers | Security | Yes |
| AT-028 | One trace links evidence, agents, risk checks, intent, order and fill/rejection | Observability | Yes |
| AT-029 | Historical case contains no evidence newer than decision timestamp | Evaluation | Yes |
| AT-030 | Rules, single-agent and multi-agent variants use identical case snapshot | Evaluation | Yes |
| AT-031 | Evaluation reports latency, cost, unsupported claims and risk violations | Evaluation | Yes |
| AT-032 | Accepted deterministic risk violations equal zero | Evaluation | Yes |
| AT-033 | Coordinator restart resumes from checkpoint or terminates safely | Failure recovery | Yes |
| AT-034 | Required audit-store failure blocks new side effects | Failure recovery | Yes |
| AT-035 | Complete fake-broker recommendation-to-fill demonstration passes | End-to-end | Yes |
| AT-036 | Alpaca paper adapter contract matches documented order state mapping | Contract | Yes |
| AT-037 | Docker image builds reproducibly and exposes the integrated commit and release version | Build | Yes |
| AT-038 | Render development deployment starts with live trading disabled and secrets absent from source | Deployment | Yes |
| AT-039 | Development Alembic migrations succeed and readiness stays false until completion | Deployment | Yes |
| AT-040 | Remote accepted and rejected recommendation paths pass against the deployed API | Post-deploy integration | Yes |
| AT-041 | Remote duplicate-intent, pause, authentication, trace and redaction checks pass | Post-deploy integration | Yes |
| AT-042 | Deployed service restart preserves durable state and resumes safely | Post-deploy recovery | Yes |
| AT-043 | Previous known-good development release can be restored without destructive database rollback | Deployment recovery | Yes |

## Required final commands

Adapt command names to the created project, then record exact commands and results in `PROGRESS.md`:

```text
uv run pytest
uv run ruff check .
uv run mypy src
docker compose config
docker build --label org.opencontainers.image.revision=<git-sha> .
```

After the local commands pass, deploy the same commit to the configured Render development environment and run the remote suite defined in `DEV_DEPLOYMENT.md`. If Alpaca paper credentials are configured, run the required read-only connectivity smoke check. The deterministic fake-broker suite remains the authoritative execution-behavior gate, while successful development deployment is a separate mandatory completion gate.


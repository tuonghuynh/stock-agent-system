# Architecture

## Principle

Model-generated judgments end at a typed recommendation boundary. Deterministic controls own authorization, calculations, workflow state, risk and brokerage side effects.

## Deployment shape

The MVP is one Python 3.13 FastAPI process with internal packages and one PostgreSQL database. Pydantic v2 defines and validates boundary schemas, SQLAlchemy 2 owns persistence and Alembic owns migrations. The execution module is a strict code and permission boundary even though it is initially deployed in the same process. No message broker or independently deployed microservice is required.

```text
User policy and temporary views
              |
              v
     Deterministic Coordinator
              |
              v
 Data/Evidence Snapshot Services
              |
       Research Agent
              |
       +------+------+
       |             |
  Portfolio path  Independent Critic
       |             |
       +------+------+
              |
      Portfolio Recommendation
              |
   Deterministic Policy/Risk Gate
              |
         Trade Intent
              |
   Separate Execution Boundary
              |
       Fake / Alpaca Paper
```

## Components

### Policy module

Owns immutable investment policies, temporary views and version resolution. It exposes read-only policy snapshots to decision runs. Only authenticated administrative APIs may create a new version; agents have no write path.

### Market-data and evidence module

Retrieves approved data, computes deterministic indicators and produces immutable evidence snapshots. External text is tagged as untrusted. Provenance and content hashes travel with every finding.

### Portfolio module

Maintains broker-reconciled positions, cash, sector exposure, pending orders and local reservations. It provides a sanitized portfolio view to the Portfolio Agent and exact values to the risk engine.

### Coordinator module

Creates `RunManifest`, executes a fixed DAG, claims durable work, enforces budgets and validates handoffs. It does not decide whether a stock is attractive. It never modifies a running objective.

### Agent runtime

Calls models through explicit role adapters. Each adapter owns its prompt, schema, allowlisted tools, timeout and cost budget. Agents do not call one another.

### Recommendation module

Stores baseline, single-agent and multi-agent recommendations. It records conflicts and converts only eligible recommendations into target-position proposals.

### Policy/risk module

Pure deterministic rules plus transactional reservation. Each rule returns an auditable result. Failure is terminal for the proposed intent; agents cannot negotiate with the gate.

### Execution module

Owns broker credentials, intent idempotency, order submission, state transitions, fills, cancellation and reconciliation. It accepts only a persisted, approved paper intent. Agents cannot reference this interface.

### Evaluation module

Replays versioned point-in-time cases through all variants, calculates metrics and produces comparison reports. Evaluation releases are isolated from the active release.

### Observability module

Emits structured audit events, traces and metrics while redacting sensitive fields. Trace IDs link all components.

## Agent contracts

### Research Agent

- **Purpose:** Extract and organize material facts.
- **Inputs:** Run manifest, evidence snapshot and policy snapshot.
- **Outputs:** Typed claims, citations, source quality, confidence, contradictions, assumptions and missing data.
- **Tools:** Read-only evidence lookup limited to the run symbol and date range.
- **Bounds:** One pass and one schema-repair attempt within the shared budget.
- **Prohibited:** Trading, sizing, policy mutation, broker/account access, delegation and executing source instructions.

### Critic Agent

- **Purpose:** Independently find weak evidence, downside cases, conflicts and policy mismatches.
- **Inputs:** Evidence snapshot first; candidate recommendation in a bounded review step.
- **Outputs:** Objections with materiality, evidence and resolved/unresolved state.
- **Tools:** Read-only source verification.
- **Bounds:** One critique pass with a maximum configured objection count.
- **Prohibited:** Rewriting the task, submitting an alternate order, contacting other agents or changing limits.

### Portfolio Agent

- **Purpose:** Synthesize evidence and criticism into a target-position proposal.
- **Inputs:** Structured research, critic result, sanitized holdings and policy snapshot.
- **Outputs:** Action, thesis, scenarios, contradictions, invalidation, confidence, horizon and target weight.
- **Tools:** Read-only portfolio summary and deterministic calculator.
- **Bounds:** Symbols and horizon are fixed by the run manifest.
- **Prohibited:** Creating orders, viewing credentials, bypassing rules or altering policy.

### Optional future Analyst Agent

Split thesis construction from the Portfolio Agent only if evaluation shows material improvement. It must reuse the same recommendation boundary; no execution change is allowed.

## Coordination

The workflow is a fixed DAG, not a conversation. The coordinator passes the smallest required typed context. All branches draw from one run-level budget. At most one repair/revision is allowed. Unresolved material conflict terminates as `NEEDS_REVIEW`; missing material data terminates as `WAIT` or rejection.

## Key data flow

1. Resolve active release and policy versions.
2. Create run manifest and trace.
3. Freeze evidence and portfolio snapshots.
4. Run deterministic baseline.
5. Run single-agent baseline for comparison.
6. Run Research, Critic and Portfolio workflow.
7. Validate recommendation schema and eligibility.
8. Evaluate deterministic rules using current broker/account state.
9. Reserve cash or shares transactionally.
10. Persist paper trade intent and idempotency key.
11. Submit through broker adapter.
12. Reconcile events, fills, cash and positions.
13. Evaluate outcome against original thesis and baselines.

## Failure paths

- **Agent unavailable:** required branch ends safely with no order; optional metrics still record the failure.
- **Malformed output:** one constrained schema repair, then failure.
- **Stale/missing market data:** risk rejection; no fallback estimate.
- **Coordinator crash:** resume from checkpoints with the same immutable manifest or terminate the run.
- **Submission response lost:** mark `UNKNOWN`, query broker by client order ID, never blindly resubmit.
- **Partial fill:** apply filled quantity, keep remaining reservation and continue monitoring.
- **Cancellation race:** process fills until broker confirms a terminal state.
- **Reconciliation mismatch:** pause new submissions and continue monitoring.
- **Trace/audit unavailable:** reject new side effects until audit durability is restored.

## Trust boundaries

1. External data → evidence ingestion: untrusted.
2. Evidence → agents: content is data, never instructions.
3. Agent output → coordinator: untrusted until schema and provenance validation.
4. Recommendation → risk gate: proposal only.
5. Risk gate → execution: typed, persisted intent only.
6. Execution → broker: credentialed paper-only boundary.


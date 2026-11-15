# Canonical Interfaces and State Machines

Names may be represented as frozen Pydantic models, dataclasses or enums, but semantics and required fields must remain stable. Boundary DTOs must use strict validation and reject unknown fields.

## RunManifest

Required fields:

```text
runId, traceId, objective, symbols, horizon, asOf,
policyVersion, releaseVersion, workflowVersion,
dataSnapshotId, modelVersions, promptVersions, toolVersions,
deadline, maxModelCalls, maxToolCalls, maxTokens, maxCost,
allowedActions, prohibitedActions, status
```

Statuses: `CREATED`, `RUNNING`, `COMPLETED`, `WAIT`, `NEEDS_REVIEW`, `FAILED`, `CANCELED`.

## EvidenceSnapshot

Contains immutable market, fundamental, event, news, portfolio and technical-indicator entries. Each entry includes:

```text
evidenceId, type, value/contentReference, sourceId, sourceUri,
publisher, sourceTimestamp, retrievedAt, contentHash,
freshnessStatus, trustClass, conflicts
```

`trustClass` is one of `PRIMARY`, `APPROVED_SECONDARY`, `UNTRUSTED_EXTERNAL`, `DERIVED_DETERMINISTIC`.

## AgentFinding

```text
findingId, agentRole, runId, claim, classification,
evidenceIds, supportingEvidence, contradictingEvidence,
confidence, assumptions, missingInformation,
analysisTimestamp, modelVersion, promptVersion
```

`classification` is `FACT`, `DERIVATION`, `INFERENCE` or `HYPOTHESIS`.

## Recommendation

```text
recommendationId, runId, variant, symbol, action,
thesis, bullCase, baseCase, bearCase,
supportingEvidenceIds, contradictingEvidenceIds,
materialConflicts, invalidationConditions,
horizon, confidence, currentWeight, targetWeight,
entryConditions, exitConditions, expiresAt, status
```

Actions: `BUY`, `SELL`, `HOLD`, `WAIT`, `NEEDS_REVIEW`.

Variants: `RULES_BASELINE`, `SINGLE_AGENT`, `MULTI_AGENT`.

## RiskDecision

```text
riskDecisionId, recommendationId, policyVersion,
accountSnapshotId, evaluatedAt, decision, checks
```

Each check contains:

```text
ruleId, passed, observedValue, limitValue, reason, evidenceTimestamp
```

Decision is `APPROVED` or `REJECTED`. There is no model override field.

## TradeIntent

```text
intentId, idempotencyKey, recommendationId, riskDecisionId,
environment, symbol, side, quantity, orderType, limitPrice,
timeInForce, expiresAt, policyVersion, createdAt, status
```

Only `environment=PAPER`, `orderType=LIMIT`, `timeInForce=DAY` and long-only sides are supported.

Statuses:

```text
CREATED → RESERVED → SUBMITTING → SUBMITTED → PARTIALLY_FILLED → FILLED
                              ↘ UNKNOWN → RECONCILING → SUBMITTED|REJECTED
SUBMITTED|PARTIALLY_FILLED → PENDING_CANCEL → CANCELED|FILLED
SUBMITTING|SUBMITTED → REJECTED|EXPIRED
```

No retry may move `UNKNOWN` to `SUBMITTING` until reconciliation proves no broker order exists.

## BrokerOrder and Fill

`BrokerOrder` stores broker order ID, stable client order ID, status, submitted/updated timestamps, requested and filled quantity, average fill price and raw-response hash.

`Fill` stores broker fill ID, order ID, quantity, price, execution time and deduplication hash.

## AuditEvent

```text
eventId, traceId, runId, intentId, eventType,
component, occurredAt, actorType, actorVersion,
inputReferences, outputReferences, durationMs,
tokenCount, estimatedCost, redactedMetadata
```

Audit events are append-only.

## Idempotency

The intent idempotency key is derived from the immutable recommendation, policy version, account, symbol, side, target delta, order parameters and expiry. A unique database constraint is required. Broker `client_order_id` is stable and derived from the persisted intent ID.

## Reservations

Cash/share reservations are created in the same database transaction that approves the intent for submission. Calculations include broker pending orders and active local reservations. Reservations decrease on fills and release only after a verified terminal state.


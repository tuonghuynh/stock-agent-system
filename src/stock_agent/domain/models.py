from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, model_validator


class BoundaryModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class RunStatus(StrEnum):
    CREATED = "CREATED"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    WAIT = "WAIT"
    NEEDS_REVIEW = "NEEDS_REVIEW"
    FAILED = "FAILED"
    CANCELED = "CANCELED"


class RunManifest(BoundaryModel):
    run_id: UUID
    trace_id: str = Field(min_length=1)
    objective: str = Field(min_length=1)
    symbols: tuple[str, ...] = Field(min_length=1)
    horizon: str = Field(min_length=1)
    as_of: datetime
    policy_version: str = Field(min_length=1)
    release_version: str = Field(min_length=1)
    workflow_version: str = Field(min_length=1)
    data_snapshot_id: UUID
    model_versions: dict[str, str]
    prompt_versions: dict[str, str]
    tool_versions: dict[str, str]
    deadline: datetime
    max_model_calls: int = Field(ge=0)
    max_tool_calls: int = Field(ge=0)
    max_tokens: int = Field(ge=0)
    max_cost: Decimal = Field(ge=0)
    allowed_actions: tuple[str, ...]
    prohibited_actions: tuple[str, ...]
    status: RunStatus

    @model_validator(mode="after")
    def validate_deadline(self) -> "RunManifest":
        if self.deadline <= self.as_of:
            raise ValueError("deadline must be after as_of")
        return self


class TrustClass(StrEnum):
    PRIMARY = "PRIMARY"
    APPROVED_SECONDARY = "APPROVED_SECONDARY"
    UNTRUSTED_EXTERNAL = "UNTRUSTED_EXTERNAL"
    DERIVED_DETERMINISTIC = "DERIVED_DETERMINISTIC"


class FreshnessStatus(StrEnum):
    FRESH = "FRESH"
    STALE = "STALE"
    UNAVAILABLE = "UNAVAILABLE"
    CONFLICTING = "CONFLICTING"


class EvidenceEntry(BoundaryModel):
    evidence_id: UUID
    type: str = Field(min_length=1)
    content_reference: str = Field(min_length=1)
    source_id: str = Field(min_length=1)
    source_uri: HttpUrl | None = None
    publisher: str = Field(min_length=1)
    source_timestamp: datetime
    retrieved_at: datetime
    content_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    freshness_status: FreshnessStatus
    trust_class: TrustClass
    conflicts: tuple[str, ...] = ()


class EvidenceSnapshot(BoundaryModel):
    snapshot_id: UUID
    run_id: UUID
    as_of: datetime
    entries: tuple[EvidenceEntry, ...] = Field(min_length=1)
    content_hash: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def prevent_future_data(self) -> "EvidenceSnapshot":
        for entry in self.entries:
            if entry.source_timestamp > self.as_of or entry.retrieved_at > self.as_of:
                raise ValueError("evidence may not be newer than snapshot as_of")
        return self


class AgentRole(StrEnum):
    RESEARCH = "RESEARCH"
    CRITIC = "CRITIC"
    PORTFOLIO = "PORTFOLIO"
    SINGLE_AGENT = "SINGLE_AGENT"


class FindingClassification(StrEnum):
    FACT = "FACT"
    DERIVATION = "DERIVATION"
    INFERENCE = "INFERENCE"
    HYPOTHESIS = "HYPOTHESIS"


class AgentFinding(BoundaryModel):
    finding_id: UUID
    agent_role: AgentRole
    run_id: UUID
    claim: str = Field(min_length=1)
    classification: FindingClassification
    evidence_ids: tuple[UUID, ...] = Field(min_length=1)
    supporting_evidence: tuple[UUID, ...]
    contradicting_evidence: tuple[UUID, ...]
    confidence: int = Field(ge=0, le=100)
    assumptions: tuple[str, ...]
    missing_information: tuple[str, ...]
    analysis_timestamp: datetime
    model_version: str = Field(min_length=1)
    prompt_version: str = Field(min_length=1)


class RecommendationAction(StrEnum):
    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"
    WAIT = "WAIT"
    NEEDS_REVIEW = "NEEDS_REVIEW"


class RecommendationVariant(StrEnum):
    RULES_BASELINE = "RULES_BASELINE"
    SINGLE_AGENT = "SINGLE_AGENT"
    MULTI_AGENT = "MULTI_AGENT"


class RecommendationStatus(StrEnum):
    PROPOSED = "PROPOSED"
    ELIGIBLE = "ELIGIBLE"
    INELIGIBLE = "INELIGIBLE"
    EXPIRED = "EXPIRED"


class Recommendation(BoundaryModel):
    recommendation_id: UUID
    run_id: UUID
    variant: RecommendationVariant
    symbol: str = Field(pattern=r"^[A-Z][A-Z0-9.-]{0,14}$")
    action: RecommendationAction
    thesis: str = Field(min_length=1)
    bull_case: str = Field(min_length=1)
    base_case: str = Field(min_length=1)
    bear_case: str = Field(min_length=1)
    supporting_evidence_ids: tuple[UUID, ...]
    contradicting_evidence_ids: tuple[UUID, ...]
    material_conflicts: tuple[str, ...]
    invalidation_conditions: tuple[str, ...] = Field(min_length=1)
    horizon: str = Field(min_length=1)
    confidence: int = Field(ge=0, le=100)
    current_weight: Decimal = Field(ge=0)
    target_weight: Decimal = Field(ge=0)
    entry_conditions: tuple[str, ...]
    exit_conditions: tuple[str, ...]
    expires_at: datetime
    status: RecommendationStatus


class RiskCheck(BoundaryModel):
    rule_id: str = Field(min_length=1)
    passed: bool
    observed_value: str
    limit_value: str
    reason: str = Field(min_length=1)
    evidence_timestamp: datetime


class RiskDecisionValue(StrEnum):
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class RiskDecision(BoundaryModel):
    risk_decision_id: UUID
    recommendation_id: UUID
    policy_version: str = Field(min_length=1)
    account_snapshot_id: UUID
    evaluated_at: datetime
    decision: RiskDecisionValue
    checks: tuple[RiskCheck, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def decision_matches_checks(self) -> "RiskDecision":
        expected = (
            RiskDecisionValue.APPROVED
            if all(check.passed for check in self.checks)
            else RiskDecisionValue.REJECTED
        )
        if self.decision != expected:
            raise ValueError("risk decision must be derived exclusively from checks")
        return self


class TradeEnvironment(StrEnum):
    PAPER = "PAPER"


class TradeSide(StrEnum):
    BUY = "BUY"
    SELL = "SELL"


class OrderType(StrEnum):
    LIMIT = "LIMIT"


class TimeInForce(StrEnum):
    DAY = "DAY"


class IntentStatus(StrEnum):
    CREATED = "CREATED"
    RESERVED = "RESERVED"
    SUBMITTING = "SUBMITTING"
    SUBMITTED = "SUBMITTED"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    FILLED = "FILLED"
    UNKNOWN = "UNKNOWN"
    RECONCILING = "RECONCILING"
    PENDING_CANCEL = "PENDING_CANCEL"
    CANCELED = "CANCELED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"
    REPLACED = "REPLACED"


class TradeIntent(BoundaryModel):
    intent_id: UUID
    idempotency_key: str = Field(pattern=r"^[0-9a-f]{64}$")
    recommendation_id: UUID
    risk_decision_id: UUID
    environment: TradeEnvironment
    symbol: str = Field(pattern=r"^[A-Z][A-Z0-9.-]{0,14}$")
    side: TradeSide
    quantity: Decimal = Field(gt=0)
    order_type: OrderType
    limit_price: Decimal = Field(gt=0)
    time_in_force: TimeInForce
    expires_at: datetime
    policy_version: str = Field(min_length=1)
    created_at: datetime
    status: IntentStatus


class AuditEvent(BoundaryModel):
    event_id: UUID
    trace_id: str = Field(min_length=1)
    run_id: UUID | None = None
    intent_id: UUID | None = None
    event_type: str = Field(min_length=1)
    component: str = Field(min_length=1)
    occurred_at: datetime
    actor_type: str = Field(min_length=1)
    actor_version: str = Field(min_length=1)
    input_references: tuple[str, ...]
    output_references: tuple[str, ...]
    duration_ms: int | None = Field(default=None, ge=0)
    token_count: int | None = Field(default=None, ge=0)
    estimated_cost: Decimal | None = Field(default=None, ge=0)
    redacted_metadata: dict[str, Any]

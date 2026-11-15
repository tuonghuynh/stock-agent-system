from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from stock_agent.domain.models import EvidenceSnapshot, RecommendationAction, RecommendationVariant


class EvaluationBoundary(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class VersionedCase(EvaluationBoundary):
    case_id: str = Field(min_length=1)
    decision_at: datetime
    snapshot: EvidenceSnapshot
    policy_version: str = Field(min_length=1)
    release_version: str = Field(min_length=1)

    @model_validator(mode="after")
    def prevent_future_leakage(self) -> "VersionedCase":
        if self.snapshot.as_of > self.decision_at:
            raise ValueError("snapshot is newer than historical decision timestamp")
        for entry in self.snapshot.entries:
            if entry.source_timestamp > self.decision_at or entry.retrieved_at > self.decision_at:
                raise ValueError("historical case contains future evidence")
        return self


class VariantOutcome(EvaluationBoundary):
    variant: RecommendationVariant
    snapshot_id: UUID
    snapshot_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    action: RecommendationAction
    confidence: int = Field(ge=0, le=100)
    target_weight: Decimal = Field(ge=0, le=100)


class ComparisonReport(EvaluationBoundary):
    case_id: str
    snapshot_id: UUID
    snapshot_hash: str
    policy_version: str
    release_version: str
    outcomes: tuple[VariantOutcome, ...]
    actions_agree: bool


class EvaluationFailure(StrEnum):
    MALFORMED_OUTPUT = "MALFORMED_OUTPUT"
    PROMPT_INJECTION = "PROMPT_INJECTION"
    STALE_DATA = "STALE_DATA"
    CONFLICTING_SOURCES = "CONFLICTING_SOURCES"
    BROKER_FAILURE = "BROKER_FAILURE"


class OutcomeMetrics(EvaluationBoundary):
    citation_validity_pct: Decimal = Field(ge=0, le=100)
    unsupported_claims: int = Field(ge=0)
    fresh_evidence_pct: Decimal = Field(ge=0, le=100)
    conflicts_detected: int = Field(ge=0)
    calibration_error: Decimal = Field(ge=0, le=1)
    return_pct: Decimal
    drawdown_pct: Decimal = Field(ge=0)
    turnover_pct: Decimal = Field(ge=0)
    latency_ms: int = Field(ge=0)
    model_calls: int = Field(ge=0)
    tool_calls: int = Field(ge=0)
    estimated_cost: Decimal = Field(ge=0)
    accepted_risk_violations: int = Field(ge=0)
    invalid_outputs: int = Field(ge=0)


class EvaluatedOutcome(EvaluationBoundary):
    outcome: VariantOutcome
    metrics: OutcomeMetrics
    failures: tuple[EvaluationFailure, ...] = ()


class VariantAggregate(EvaluationBoundary):
    variant: RecommendationVariant
    case_count: int = Field(gt=0)
    citation_validity_pct: Decimal
    unsupported_claims: int
    fresh_evidence_pct: Decimal
    conflicts_detected: int
    calibration_error: Decimal
    return_pct: Decimal
    maximum_drawdown_pct: Decimal
    turnover_pct: Decimal
    latency_ms: int
    model_calls: int
    tool_calls: int
    estimated_cost: Decimal
    accepted_risk_violations: int
    abstentions: int
    needs_review: int
    invalid_outputs: int
    failures: dict[EvaluationFailure, int]


class EvaluationReport(EvaluationBoundary):
    schema_version: str = Field(min_length=1)
    release_version: str = Field(min_length=1)
    policy_version: str = Field(min_length=1)
    case_ids: tuple[str, ...] = Field(min_length=1)
    snapshot_hashes: tuple[str, ...] = Field(min_length=1)
    variants: tuple[VariantAggregate, ...] = Field(min_length=3, max_length=3)
    accepted_risk_violations: int = Field(ge=0)
    fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")


class RegressionThresholds(EvaluationBoundary):
    minimum_citation_validity_pct: Decimal = Field(ge=0, le=100)
    maximum_unsupported_claims: int = Field(ge=0)
    maximum_calibration_error: Decimal = Field(ge=0, le=1)
    maximum_drawdown_pct: Decimal = Field(ge=0)
    maximum_latency_ms: int = Field(ge=0)
    maximum_estimated_cost: Decimal = Field(ge=0)


class RegressionDecision(EvaluationBoundary):
    passed: bool
    violations: tuple[str, ...]

from datetime import datetime
from decimal import Decimal
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

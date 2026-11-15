from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from stock_agent.domain.models import EvidenceSnapshot, Recommendation
from stock_agent.evidence.indicators import TechnicalIndicators


class BaselineBoundary(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class FundamentalScores(BaselineBoundary):
    """Deterministically derived, evidence-backed fundamental subscores."""

    quality: Decimal = Field(ge=0, le=100)
    growth: Decimal = Field(ge=0, le=100)
    valuation: Decimal = Field(ge=0, le=100)
    evidence_ids: tuple[UUID, ...] = Field(min_length=1)
    calculated_at: datetime


class BaselineInput(BaselineBoundary):
    snapshot: EvidenceSnapshot
    policy_version: str = Field(min_length=1)
    release_version: str = Field(min_length=1)
    symbol: str = Field(pattern=r"^[A-Z][A-Z0-9.-]{0,14}$")
    horizon: str = Field(min_length=1)
    current_weight: Decimal = Field(ge=0, le=100)
    current_price: Decimal = Field(gt=0)
    fundamentals: FundamentalScores
    technicals: TechnicalIndicators
    next_market_close: datetime

    @model_validator(mode="after")
    def enforce_point_in_time_and_provenance(self) -> "BaselineInput":
        as_of = self.snapshot.as_of
        if self.fundamentals.calculated_at > as_of:
            raise ValueError("fundamental scores are newer than the evidence snapshot")
        if self.technicals.as_of != as_of or self.technicals.latest_bar_at > as_of:
            raise ValueError("technical indicators must be point-in-time at snapshot as_of")
        available = {entry.evidence_id for entry in self.snapshot.entries}
        if not set(self.fundamentals.evidence_ids).issubset(available):
            raise ValueError("fundamental score references evidence outside the snapshot")
        if self.next_market_close <= as_of:
            raise ValueError("next_market_close must be after snapshot as_of")
        return self


class FactorScores(BaselineBoundary):
    quality: Decimal = Field(ge=0, le=100)
    growth: Decimal = Field(ge=0, le=100)
    valuation: Decimal = Field(ge=0, le=100)
    trend: Decimal = Field(ge=0, le=100)
    momentum: Decimal = Field(ge=0, le=100)
    composite: Decimal = Field(ge=0, le=100)


class BaselineResult(BaselineBoundary):
    recommendation: Recommendation
    snapshot_id: UUID
    snapshot_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    policy_version: str = Field(min_length=1)
    release_version: str = Field(min_length=1)
    factors: FactorScores

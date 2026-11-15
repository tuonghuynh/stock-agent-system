"""Strict inputs and outputs for deterministic portfolio synthesis."""

from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from stock_agent.domain.models import AgentFinding, Recommendation, RecommendationAction


class PortfolioBoundary(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class CriticDisposition(StrEnum):
    APPROVED = "APPROVED"
    REVISE = "REVISE"
    REJECTED = "REJECTED"
    NEEDS_REVIEW = "NEEDS_REVIEW"


class CritiqueInput(PortfolioBoundary):
    disposition: CriticDisposition
    objections: tuple[str, ...]
    unresolved_material_conflicts: tuple[str, ...]
    evidence_ids: tuple[UUID, ...]


class PortfolioDraft(PortfolioBoundary):
    """Untrusted analytical proposal; never an execution authorization."""

    symbol: str = Field(pattern=r"^[A-Z][A-Z0-9.-]{0,14}$")
    horizon: str = Field(min_length=1)
    action: RecommendationAction
    thesis: str = Field(min_length=1)
    bull_case: str = Field(min_length=1)
    base_case: str = Field(min_length=1)
    bear_case: str = Field(min_length=1)
    supporting_evidence_ids: tuple[UUID, ...] = Field(min_length=1)
    contradicting_evidence_ids: tuple[UUID, ...]
    material_conflicts: tuple[str, ...]
    invalidation_conditions: tuple[str, ...] = Field(min_length=1)
    confidence: int = Field(ge=0, le=100)
    target_weight: Decimal = Field(ge=0, le=100)
    entry_conditions: tuple[str, ...]
    exit_conditions: tuple[str, ...]


class PortfolioSynthesisInput(PortfolioBoundary):
    run_id: UUID
    symbol: str = Field(pattern=r"^[A-Z][A-Z0-9.-]{0,14}$")
    horizon: str = Field(min_length=1)
    as_of: datetime
    next_market_close: datetime
    snapshot_id: UUID
    snapshot_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    evidence_ids: tuple[UUID, ...] = Field(min_length=1)
    policy_version: str = Field(min_length=1)
    release_version: str = Field(min_length=1)
    workflow_version: str = Field(min_length=1)
    model_version: str = Field(min_length=1)
    prompt_version: str = Field(min_length=1)
    current_weight: Decimal = Field(ge=0, le=100)
    maximum_target_weight: Decimal = Field(gt=0, le=100)
    material_data_complete: bool
    research_findings: tuple[AgentFinding, ...] = Field(min_length=1)
    critique: CritiqueInput
    draft: PortfolioDraft

    @model_validator(mode="after")
    def enforce_frozen_context_and_provenance(self) -> "PortfolioSynthesisInput":
        if self.next_market_close <= self.as_of:
            raise ValueError("next market close must follow the frozen run timestamp")
        if self.draft.symbol != self.symbol or self.draft.horizon != self.horizon:
            raise ValueError("portfolio draft cannot change symbol or horizon")
        if self.draft.target_weight > self.maximum_target_weight:
            raise ValueError("portfolio target exceeds its proposal bound")
        available = set(self.evidence_ids)
        proposed = set(self.draft.supporting_evidence_ids) | set(
            self.draft.contradicting_evidence_ids
        )
        if not proposed.issubset(available):
            raise ValueError("portfolio draft references evidence outside the frozen snapshot")
        if not set(self.critique.evidence_ids).issubset(available):
            raise ValueError("critique references evidence outside the frozen snapshot")
        for finding in self.research_findings:
            finding_evidence = (
                set(finding.evidence_ids)
                | set(finding.supporting_evidence)
                | set(finding.contradicting_evidence)
            )
            if finding.run_id != self.run_id:
                raise ValueError("research finding belongs to another run")
            if finding.analysis_timestamp != self.as_of:
                raise ValueError("research finding must use the frozen run timestamp")
            if not finding_evidence.issubset(available):
                raise ValueError("research finding references evidence outside the snapshot")
        return self


class PortfolioSynthesisResult(PortfolioBoundary):
    recommendation: Recommendation
    snapshot_id: UUID
    snapshot_hash: str
    policy_version: str
    release_version: str
    workflow_version: str
    model_version: str
    prompt_version: str
    execution_authorized: Literal[False] = False
    requires_deterministic_risk: Literal[True] = True


"""Strict immutable inputs and outputs for independent recommendation critique."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from stock_agent.domain.models import AgentFinding, AgentRole, Recommendation


class CriticBoundary(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class CriticInput(CriticBoundary):
    """Frozen public artifacts; hidden reasoning and mutable authority are absent."""

    run_id: UUID
    objective: str = Field(min_length=1)
    symbol: str = Field(pattern=r"^[A-Z][A-Z0-9.-]{0,14}$")
    horizon: str = Field(min_length=1)
    as_of: datetime
    candidate: Recommendation
    findings: tuple[AgentFinding, ...] = Field(min_length=1)
    available_evidence_ids: frozenset[UUID] = Field(min_length=1)
    maximum_target_weight: Decimal = Field(ge=0, le=100)
    maximum_objections: int = Field(ge=1, le=20)

    @model_validator(mode="after")
    def validate_frozen_artifacts(self) -> CriticInput:
        if self.candidate.run_id != self.run_id:
            raise ValueError("candidate belongs to another run")
        if self.candidate.symbol != self.symbol or self.candidate.horizon != self.horizon:
            raise ValueError("candidate cannot change symbol or horizon")
        candidate_evidence = (
            set(self.candidate.supporting_evidence_ids)
            | set(self.candidate.contradicting_evidence_ids)
        )
        if not candidate_evidence.issubset(self.available_evidence_ids):
            raise ValueError("candidate references evidence outside the frozen snapshot")
        for finding in self.findings:
            if finding.agent_role is AgentRole.CRITIC:
                raise ValueError("critic cannot review its own findings")
            if finding.run_id != self.run_id:
                raise ValueError("finding belongs to another run")
            if finding.analysis_timestamp != self.as_of:
                raise ValueError("finding timestamp must equal the frozen run timestamp")
            finding_evidence = (
                set(finding.evidence_ids)
                | set(finding.supporting_evidence)
                | set(finding.contradicting_evidence)
            )
            if not finding_evidence.issubset(self.available_evidence_ids):
                raise ValueError("finding references evidence outside the frozen snapshot")
        return self


class ObjectionKind(StrEnum):
    UNSUPPORTED_CLAIM = "UNSUPPORTED_CLAIM"
    CONTRADICTION = "CONTRADICTION"
    CONCENTRATION = "CONCENTRATION"
    DOWNSIDE = "DOWNSIDE"
    UNCERTAINTY = "UNCERTAINTY"
    MATERIAL_CONFLICT = "MATERIAL_CONFLICT"
    LOW_CONFIDENCE = "LOW_CONFIDENCE"
    EXPIRED = "EXPIRED"


class Materiality(StrEnum):
    MATERIAL = "MATERIAL"
    NON_MATERIAL = "NON_MATERIAL"


class Objection(CriticBoundary):
    objection_id: str = Field(pattern=r"^OBJ-[0-9]{3}$")
    kind: ObjectionKind
    materiality: Materiality
    summary: str = Field(min_length=1)
    evidence_ids: tuple[UUID, ...]
    resolved: bool


class CritiqueDisposition(StrEnum):
    CLEAR = "CLEAR"
    REVISE = "REVISE"
    NEEDS_REVIEW = "NEEDS_REVIEW"
    WAIT = "WAIT"


class CriticResult(CriticBoundary):
    run_id: UUID
    candidate_recommendation_id: UUID
    candidate_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    disposition: CritiqueDisposition
    objections: tuple[Objection, ...]
    unresolved_material_conflicts: tuple[str, ...]
    blocks_intent: bool
    execution_authorized: Literal[False] = False

    @model_validator(mode="after")
    def enforce_safe_disposition(self) -> CriticResult:
        material_unresolved = any(
            item.materiality is Materiality.MATERIAL and not item.resolved
            for item in self.objections
        )
        if material_unresolved and not self.blocks_intent:
            raise ValueError("unresolved material objections must block intent creation")
        if self.disposition is CritiqueDisposition.CLEAR and self.blocks_intent:
            raise ValueError("a clear critique cannot block the candidate")
        if self.disposition is not CritiqueDisposition.CLEAR and not self.blocks_intent:
            raise ValueError("non-clear critique must block the candidate")
        return self

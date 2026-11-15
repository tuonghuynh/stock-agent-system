"""Strict task-local contracts for the Research Agent boundary."""

from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from stock_agent.domain.models import AgentFinding, EvidenceSnapshot, FindingClassification


class ResearchModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class ResearchDimension(StrEnum):
    FUNDAMENTALS = "FUNDAMENTALS"
    VALUATION = "VALUATION"
    TECHNICALS = "TECHNICALS"
    CATALYSTS = "CATALYSTS"
    RISKS = "RISKS"


class ResearchRequest(ResearchModel):
    run_id: UUID
    objective: str = Field(min_length=1)
    symbol: str = Field(pattern=r"^[A-Z][A-Z0-9.-]{0,14}$")
    horizon: str = Field(min_length=1)
    snapshot: EvidenceSnapshot
    model_version: str = Field(min_length=1)
    prompt_version: str = Field(min_length=1)


class OpaqueEvidence(ResearchModel):
    evidence_id: UUID
    reference: str = Field(pattern=r"^evidence:[0-9a-f-]+:[0-9a-f]{64}$")
    content_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_timestamp: datetime
    trust_class: str
    conflicts: tuple[str, ...]


class ResearchGatewayCall(ResearchModel):
    run_id: UUID
    objective: str
    symbol: str
    horizon: str
    as_of: datetime
    evidence: tuple[OpaqueEvidence, ...] = Field(min_length=1)
    required_dimensions: tuple[ResearchDimension, ...]
    allowed_tools: tuple[str, ...] = ("evidence_lookup",)
    prohibited_capabilities: tuple[str, ...] = (
        "broker_access",
        "account_access",
        "policy_mutation",
        "workflow_mutation",
        "delegation",
    )


class ResearchFindingDraft(ResearchModel):
    dimension: ResearchDimension
    claim: str = Field(min_length=1)
    classification: FindingClassification
    evidence_ids: tuple[UUID, ...] = Field(min_length=1)
    supporting_evidence: tuple[UUID, ...]
    contradicting_evidence: tuple[UUID, ...]
    confidence: int = Field(ge=0, le=100)
    assumptions: tuple[str, ...]
    missing_information: tuple[str, ...]
    analysis_timestamp: datetime


class ResearchDraft(ResearchModel):
    symbol: str = Field(pattern=r"^[A-Z][A-Z0-9.-]{0,14}$")
    horizon: str = Field(min_length=1)
    findings: tuple[ResearchFindingDraft, ...] = Field(min_length=1)


class ResearchStatus(StrEnum):
    VALIDATED = "VALIDATED"
    WAIT = "WAIT"


class ResearchResult(ResearchModel):
    status: ResearchStatus
    findings: tuple[AgentFinding, ...] = ()
    material_conflicts: tuple[str, ...] = ()
    missing_information: tuple[str, ...] = ()
    error_codes: tuple[str, ...] = ()

"""Strict immutable DTOs for the untrusted model boundary."""

from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from stock_agent.domain.models import (
    AgentFinding,
    Recommendation,
    RecommendationAction,
)


class GatewayModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class ToolSpec(GatewayModel):
    name: str = Field(pattern=r"^[a-z][a-z0-9_]{0,63}$")
    version: str = Field(min_length=1)
    read_only: bool


class FrozenModelContext(GatewayModel):
    run_id: UUID
    objective: str = Field(min_length=1)
    symbol: str = Field(pattern=r"^[A-Z][A-Z0-9.-]{0,14}$")
    horizon: str = Field(min_length=1)
    as_of: datetime
    evidence_ids: tuple[UUID, ...] = Field(min_length=1)
    evidence_references: tuple[str, ...] = Field(min_length=1)
    model_version: str = Field(min_length=1)
    prompt_version: str = Field(min_length=1)
    schema_version: str = Field(min_length=1)
    policy_version: str = Field(min_length=1)
    release_version: str = Field(min_length=1)
    allowed_tools: tuple[ToolSpec, ...]
    prohibited_capabilities: tuple[str, ...] = (
        "broker_access",
        "credential_access",
        "policy_mutation",
        "workflow_mutation",
        "tool_mutation",
    )


class ModelBudget(GatewayModel):
    max_calls: int = Field(ge=1, le=2)
    max_tokens: int = Field(gt=0)
    max_cost: Decimal = Field(gt=0)
    deadline: datetime


class ModelCall(GatewayModel):
    context: FrozenModelContext
    output_schema: dict[str, object]
    repair: bool = False
    validation_error_code: str | None = None


class ModelResponse(GatewayModel):
    content: str
    token_count: int = Field(ge=0)
    estimated_cost: Decimal = Field(ge=0)
    completed_at: datetime


class ToolCallDraft(GatewayModel):
    name: str = Field(pattern=r"^[a-z][a-z0-9_]{0,63}$")
    arguments: dict[str, str]


class FindingDraft(GatewayModel):
    claim: str = Field(min_length=1)
    classification: str = Field(pattern=r"^(FACT|DERIVATION|INFERENCE|HYPOTHESIS)$")
    evidence_ids: tuple[UUID, ...] = Field(min_length=1)
    supporting_evidence: tuple[UUID, ...]
    contradicting_evidence: tuple[UUID, ...]
    confidence: int = Field(ge=0, le=100)
    assumptions: tuple[str, ...]
    missing_information: tuple[str, ...]
    analysis_timestamp: datetime


class SingleAgentDraft(GatewayModel):
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
    findings: tuple[FindingDraft, ...] = Field(min_length=1)
    tool_calls: tuple[ToolCallDraft, ...] = ()


class GatewayStatus(StrEnum):
    VALIDATED = "VALIDATED"
    SAFE_FAILURE = "SAFE_FAILURE"


class GatewayResult(GatewayModel):
    status: GatewayStatus
    action: RecommendationAction
    recommendation: Recommendation | None = None
    findings: tuple[AgentFinding, ...] = ()
    calls_used: int
    tokens_used: int
    cost_used: Decimal
    error_codes: tuple[str, ...] = ()


"""Trusted validation wrapper around an untrusted one-pass research gateway."""

from __future__ import annotations

import hashlib
from typing import Protocol
from uuid import UUID, uuid5

from pydantic import ValidationError

from stock_agent.agents.research.models import (
    OpaqueEvidence,
    ResearchDimension,
    ResearchDraft,
    ResearchGatewayCall,
    ResearchRequest,
    ResearchResult,
    ResearchStatus,
)
from stock_agent.domain.models import AgentFinding, AgentRole, FreshnessStatus

_IDENTITY_NAMESPACE = UUID("b5da5516-aee4-4307-aa41-4a7d49c02666")
_REQUIRED_DIMENSIONS = tuple(ResearchDimension)


class ResearchGateway(Protocol):
    """One bounded analytical call; implementations expose no mutable tools."""

    def research(self, call: ResearchGatewayCall) -> object: ...


class ResearchAgent:
    def __init__(self, gateway: ResearchGateway) -> None:
        self._gateway = gateway

    def run(self, request: ResearchRequest) -> ResearchResult:
        self._validate_request(request)
        unsafe = tuple(
            entry
            for entry in request.snapshot.entries
            if entry.freshness_status in {FreshnessStatus.STALE, FreshnessStatus.UNAVAILABLE}
        )
        conflicts = tuple(
            conflict for entry in request.snapshot.entries for conflict in entry.conflicts
        )
        if unsafe:
            return ResearchResult(
                status=ResearchStatus.WAIT,
                material_conflicts=conflicts,
                missing_information=tuple(
                    f"{entry.type}:{entry.freshness_status.value}" for entry in unsafe
                ),
                error_codes=("MATERIAL_EVIDENCE_UNSAFE",),
            )
        call = self._call(request)
        raw = self._gateway.research(call)
        try:
            draft = ResearchDraft.model_validate(raw, strict=True)
            findings = self._validate_and_convert(request, draft)
        except (ValidationError, ValueError, TypeError):
            return ResearchResult(
                status=ResearchStatus.WAIT,
                material_conflicts=conflicts,
                error_codes=("INVALID_RESEARCH_OUTPUT",),
            )
        return ResearchResult(
            status=ResearchStatus.VALIDATED,
            findings=findings,
            material_conflicts=conflicts,
            missing_information=tuple(
                item for finding in findings for item in finding.missing_information
            ),
        )

    @staticmethod
    def _validate_request(request: ResearchRequest) -> None:
        if request.run_id != request.snapshot.run_id:
            raise ValueError("research run must match the immutable evidence snapshot")

    @staticmethod
    def _call(request: ResearchRequest) -> ResearchGatewayCall:
        return ResearchGatewayCall(
            run_id=request.run_id,
            objective=request.objective,
            symbol=request.symbol,
            horizon=request.horizon,
            as_of=request.snapshot.as_of,
            evidence=tuple(
                OpaqueEvidence(
                    evidence_id=entry.evidence_id,
                    reference=(
                        f"evidence:{entry.evidence_id}:"
                        f"{hashlib.sha256(entry.content_reference.encode()).hexdigest()}"
                    ),
                    content_hash=entry.content_hash,
                    source_timestamp=entry.source_timestamp,
                    trust_class=entry.trust_class.value,
                    conflicts=entry.conflicts,
                )
                for entry in request.snapshot.entries
            ),
            required_dimensions=_REQUIRED_DIMENSIONS,
        )

    @staticmethod
    def _validate_and_convert(
        request: ResearchRequest, draft: ResearchDraft
    ) -> tuple[AgentFinding, ...]:
        if draft.symbol != request.symbol or draft.horizon != request.horizon:
            raise ValueError("research output cannot change symbol or horizon")
        dimensions = tuple(finding.dimension for finding in draft.findings)
        if len(dimensions) != len(set(dimensions)) or set(dimensions) != set(_REQUIRED_DIMENSIONS):
            raise ValueError("research output requires exactly one finding per dimension")
        available = {entry.evidence_id for entry in request.snapshot.entries}
        findings: list[AgentFinding] = []
        for item in draft.findings:
            cited = (
                set(item.evidence_ids)
                | set(item.supporting_evidence)
                | set(item.contradicting_evidence)
            )
            if not cited.issubset(available):
                raise ValueError("research finding cites evidence outside the snapshot")
            if item.analysis_timestamp != request.snapshot.as_of:
                raise ValueError("research timestamp must equal snapshot as_of")
            identity = (
                f"{request.run_id}:{item.dimension.value}:{item.claim}:"
                f"{','.join(sorted(str(value) for value in item.evidence_ids))}"
            )
            findings.append(
                AgentFinding(
                    finding_id=uuid5(_IDENTITY_NAMESPACE, identity),
                    agent_role=AgentRole.RESEARCH,
                    run_id=request.run_id,
                    claim=item.claim,
                    classification=item.classification,
                    evidence_ids=item.evidence_ids,
                    supporting_evidence=item.supporting_evidence,
                    contradicting_evidence=item.contradicting_evidence,
                    confidence=item.confidence,
                    assumptions=item.assumptions,
                    missing_information=item.missing_information,
                    analysis_timestamp=item.analysis_timestamp,
                    model_version=request.model_version,
                    prompt_version=request.prompt_version,
                )
            )
        return tuple(findings)

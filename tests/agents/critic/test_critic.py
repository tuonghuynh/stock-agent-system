from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID

import pytest
from pydantic import ValidationError

from stock_agent.agents.critic import (
    CriticInput,
    CritiqueDisposition,
    DeterministicCritic,
    ObjectionKind,
)
from stock_agent.domain.models import (
    AgentFinding,
    AgentRole,
    FindingClassification,
    Recommendation,
    RecommendationAction,
    RecommendationStatus,
    RecommendationVariant,
)

NOW = datetime(2026, 11, 14, 20, tzinfo=UTC)
RUN_ID = UUID("10000000-0000-0000-0000-000000000001")
RECOMMENDATION_ID = UUID("20000000-0000-0000-0000-000000000001")
EVIDENCE_ID = UUID("30000000-0000-0000-0000-000000000001")
OTHER_EVIDENCE_ID = UUID("30000000-0000-0000-0000-000000000002")


def candidate(**updates: object) -> Recommendation:
    values: dict[str, object] = {
        "recommendation_id": RECOMMENDATION_ID,
        "run_id": RUN_ID,
        "variant": RecommendationVariant.MULTI_AGENT,
        "symbol": "AAPL",
        "action": RecommendationAction.BUY,
        "thesis": "Evidence supports a bounded position increase",
        "bull_case": "Growth remains durable",
        "base_case": "Current fundamentals persist",
        "bear_case": "Demand weakens",
        "supporting_evidence_ids": (EVIDENCE_ID,),
        "contradicting_evidence_ids": (),
        "material_conflicts": (),
        "invalidation_conditions": ("Revenue growth turns negative",),
        "horizon": "20 trading days",
        "confidence": 75,
        "current_weight": Decimal("2"),
        "target_weight": Decimal("4"),
        "entry_conditions": ("Risk gates pass",),
        "exit_conditions": ("Thesis invalidates",),
        "expires_at": NOW + timedelta(hours=20),
        "status": RecommendationStatus.PROPOSED,
    }
    values.update(updates)
    return Recommendation.model_validate(values, strict=True)


def finding(**updates: object) -> AgentFinding:
    values: dict[str, object] = {
        "finding_id": UUID("40000000-0000-0000-0000-000000000001"),
        "agent_role": AgentRole.RESEARCH,
        "run_id": RUN_ID,
        "claim": "Revenue growth is positive",
        "classification": FindingClassification.FACT,
        "evidence_ids": (EVIDENCE_ID,),
        "supporting_evidence": (EVIDENCE_ID,),
        "contradicting_evidence": (),
        "confidence": 80,
        "assumptions": (),
        "missing_information": (),
        "analysis_timestamp": NOW,
        "model_version": "fake-model-1",
        "prompt_version": "research-1",
    }
    values.update(updates)
    return AgentFinding.model_validate(values, strict=True)


def review(
    *, proposed: Recommendation | None = None, findings: tuple[AgentFinding, ...] | None = None
) -> CriticInput:
    return CriticInput(
        run_id=RUN_ID,
        objective="Evaluate AAPL from the frozen snapshot",
        symbol="AAPL",
        horizon="20 trading days",
        as_of=NOW,
        candidate=proposed or candidate(),
        findings=findings or (finding(),),
        available_evidence_ids=frozenset({EVIDENCE_ID, OTHER_EVIDENCE_ID}),
        maximum_target_weight=Decimal("10"),
        maximum_objections=10,
    )


def test_clear_candidate_is_repeatable_but_never_authorizes_execution() -> None:
    first = DeterministicCritic().review(review())
    second = DeterministicCritic().review(review())
    assert first == second
    assert first.disposition is CritiqueDisposition.CLEAR
    assert not first.blocks_intent
    assert first.execution_authorized is False
    assert first.candidate_recommendation_id == RECOMMENDATION_ID


def test_at008_unresolved_material_conflict_needs_review_and_blocks_intent() -> None:
    proposed = candidate(
        material_conflicts=("Primary filing and approved feed disagree on revenue",)
    )
    result = DeterministicCritic().review(review(proposed=proposed))
    assert result.disposition is CritiqueDisposition.NEEDS_REVIEW
    assert result.blocks_intent
    assert result.execution_authorized is False
    assert any(item.kind is ObjectionKind.MATERIAL_CONFLICT for item in result.objections)
    assert result.unresolved_material_conflicts


def test_at008_contradicted_support_needs_review() -> None:
    source = finding(contradicting_evidence=(EVIDENCE_ID,))
    result = DeterministicCritic().review(review(findings=(source,)))
    assert result.disposition is CritiqueDisposition.NEEDS_REVIEW
    assert any(item.kind is ObjectionKind.CONTRADICTION for item in result.objections)


def test_rec006_low_confidence_or_missing_information_cannot_proceed() -> None:
    low = DeterministicCritic().review(review(proposed=candidate(confidence=64)))
    assert low.disposition is CritiqueDisposition.WAIT
    assert low.blocks_intent

    incomplete = DeterministicCritic().review(
        review(findings=(finding(missing_information=("Current debt covenant",)),))
    )
    assert incomplete.disposition is CritiqueDisposition.REVISE
    assert incomplete.blocks_intent


def test_unsupported_claim_and_concentration_force_revision() -> None:
    proposed = candidate(
        supporting_evidence_ids=(OTHER_EVIDENCE_ID,), target_weight=Decimal("11")
    )
    result = DeterministicCritic().review(review(proposed=proposed))
    assert result.disposition is CritiqueDisposition.REVISE
    assert {item.kind for item in result.objections} >= {
        ObjectionKind.UNSUPPORTED_CLAIM,
        ObjectionKind.CONCENTRATION,
    }


def test_input_rejects_untrusted_authority_fields_and_foreign_evidence() -> None:
    payload = review().model_dump()
    payload["broker_tool"] = "submit_order"
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        CriticInput.model_validate(payload, strict=True)

    with pytest.raises(ValidationError, match="outside the frozen snapshot"):
        review(proposed=candidate(supporting_evidence_ids=(UUID(int=999),)))


def test_input_excludes_hidden_reasoning_and_rejects_future_findings() -> None:
    payload = review().model_dump()
    payload["research_chain_of_thought"] = "hidden reasoning"
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        CriticInput.model_validate(payload, strict=True)

    with pytest.raises(ValidationError, match="frozen run timestamp"):
        review(findings=(finding(analysis_timestamp=NOW + timedelta(seconds=1)),))


def test_critic_does_not_mutate_frozen_candidate() -> None:
    proposed = candidate(material_conflicts=("material disagreement",))
    before = proposed.model_dump_json()
    DeterministicCritic().review(review(proposed=proposed))
    assert proposed.model_dump_json() == before
    with pytest.raises(ValidationError):
        proposed.confidence = 100  # type: ignore[misc]

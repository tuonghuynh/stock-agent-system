from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID

import pytest
from pydantic import ValidationError

from stock_agent.agents.portfolio import (
    CriticDisposition,
    CritiqueInput,
    PortfolioDraft,
    PortfolioSynthesisInput,
    PortfolioSynthesizer,
)
from stock_agent.domain.models import (
    AgentFinding,
    AgentRole,
    FindingClassification,
    RecommendationAction,
    RecommendationStatus,
    RecommendationVariant,
)

NOW = datetime(2026, 11, 14, 20, tzinfo=UTC)
RUN_ID = UUID("10000000-0000-0000-0000-000000000001")
SNAPSHOT_ID = UUID("20000000-0000-0000-0000-000000000001")
EVIDENCE_ID = UUID("30000000-0000-0000-0000-000000000001")


def finding() -> AgentFinding:
    return AgentFinding(
        finding_id=UUID("40000000-0000-0000-0000-000000000001"),
        agent_role=AgentRole.RESEARCH,
        run_id=RUN_ID,
        claim="Revenue growth is positive",
        classification=FindingClassification.FACT,
        evidence_ids=(EVIDENCE_ID,),
        supporting_evidence=(EVIDENCE_ID,),
        contradicting_evidence=(),
        confidence=80,
        assumptions=("Reported figures are accurate",),
        missing_information=(),
        analysis_timestamp=NOW,
        model_version="fake-model-1",
        prompt_version="research-1",
    )


def synthesis_input(
    *,
    confidence: int = 75,
    complete: bool = True,
    disposition: CriticDisposition = CriticDisposition.APPROVED,
    conflicts: tuple[str, ...] = (),
    symbol: str = "AAPL",
    draft_symbol: str = "AAPL",
    target: str = "4",
    contradictory: bool = False,
) -> PortfolioSynthesisInput:
    return PortfolioSynthesisInput(
        run_id=RUN_ID,
        symbol=symbol,
        horizon="20 trading days",
        as_of=NOW,
        next_market_close=NOW + timedelta(hours=20),
        snapshot_id=SNAPSHOT_ID,
        snapshot_hash="a" * 64,
        evidence_ids=(EVIDENCE_ID,),
        policy_version="1",
        release_version="release-1",
        workflow_version="workflow-1",
        model_version="fake-model-1",
        prompt_version="portfolio-1",
        current_weight=Decimal("2"),
        maximum_target_weight=Decimal("10"),
        material_data_complete=complete,
        research_findings=(finding(),),
        critique=CritiqueInput(
            disposition=disposition,
            objections=(
                ("Valuation could compress",)
                if disposition is not CriticDisposition.APPROVED
                else ()
            ),
            unresolved_material_conflicts=conflicts,
            evidence_ids=(EVIDENCE_ID,),
        ),
        draft=PortfolioDraft(
            symbol=draft_symbol,
            horizon="20 trading days",
            action=RecommendationAction.BUY,
            thesis="Quality and growth support a staged position",
            bull_case="Growth accelerates",
            base_case="Growth remains durable",
            bear_case="Valuation compresses",
            supporting_evidence_ids=(EVIDENCE_ID,),
            contradicting_evidence_ids=(EVIDENCE_ID,) if contradictory else (),
            material_conflicts=(),
            invalidation_conditions=("Revenue growth turns negative",),
            confidence=confidence,
            target_weight=Decimal(target),
            entry_conditions=("Deterministic risk gates pass",),
            exit_conditions=("Thesis invalidates",),
        ),
    )


def test_rec003_rec005_complete_multi_agent_proposal_is_deterministic() -> None:
    inputs = synthesis_input()
    first = PortfolioSynthesizer().synthesize(inputs)
    second = PortfolioSynthesizer().synthesize(inputs)

    assert first == second
    recommendation = first.recommendation
    assert recommendation.variant is RecommendationVariant.MULTI_AGENT
    assert recommendation.action is RecommendationAction.BUY
    assert recommendation.status is RecommendationStatus.PROPOSED
    assert recommendation.current_weight == Decimal("2")
    assert recommendation.target_weight == Decimal("4")
    assert recommendation.expires_at == NOW + timedelta(hours=20)
    assert recommendation.bull_case and recommendation.base_case and recommendation.bear_case
    assert recommendation.contradicting_evidence_ids == ()
    assert recommendation.invalidation_conditions
    assert recommendation.entry_conditions and recommendation.exit_conditions
    assert first.policy_version == "1"
    assert first.snapshot_id == SNAPSHOT_ID
    assert first.execution_authorized is False
    assert first.requires_deterministic_risk is True


def test_at009_confidence_below_65_is_ineligible_wait_with_no_target_delta() -> None:
    result = PortfolioSynthesizer().synthesize(synthesis_input(confidence=64))
    recommendation = result.recommendation

    assert recommendation.action is RecommendationAction.WAIT
    assert recommendation.status is RecommendationStatus.INELIGIBLE
    assert recommendation.target_weight == recommendation.current_weight
    assert result.execution_authorized is False


@pytest.mark.parametrize(
    ("inputs", "expected"),
    [
        (synthesis_input(complete=False), RecommendationAction.WAIT),
        (
            synthesis_input(
                disposition=CriticDisposition.NEEDS_REVIEW,
                conflicts=("Research and critic disagree on cash flow quality",),
            ),
            RecommendationAction.NEEDS_REVIEW,
        ),
        (
            synthesis_input(disposition=CriticDisposition.REJECTED),
            RecommendationAction.NEEDS_REVIEW,
        ),
    ],
)
def test_missing_data_or_critic_rejection_cannot_create_eligible_proposal(
    inputs: PortfolioSynthesisInput, expected: RecommendationAction
) -> None:
    result = PortfolioSynthesizer().synthesize(inputs)
    assert result.recommendation.action is expected
    assert result.recommendation.status is RecommendationStatus.INELIGIBLE
    assert result.recommendation.target_weight == result.recommendation.current_weight
    assert not result.execution_authorized


def test_untrusted_draft_cannot_change_symbol_or_exceed_target_bound() -> None:
    with pytest.raises(ValidationError, match="cannot change symbol"):
        synthesis_input(draft_symbol="TSLA")
    with pytest.raises(ValidationError, match="exceeds its proposal bound"):
        synthesis_input(target="11")


def test_same_evidence_cannot_support_and_contradict_an_eligible_trade() -> None:
    result = PortfolioSynthesizer().synthesize(synthesis_input(contradictory=True))

    assert result.recommendation.action is RecommendationAction.NEEDS_REVIEW
    assert result.recommendation.status is RecommendationStatus.INELIGIBLE
    assert result.recommendation.target_weight == result.recommendation.current_weight
    assert "both supporting and contradicting" in result.recommendation.material_conflicts[0]
    assert result.execution_authorized is False


def test_research_must_match_frozen_run_timestamp_and_evidence() -> None:
    unsafe = finding().model_copy(update={"analysis_timestamp": NOW + timedelta(seconds=1)})
    payload = synthesis_input().model_dump()
    payload["research_findings"] = (unsafe,)
    with pytest.raises(ValidationError, match="frozen run timestamp"):
        PortfolioSynthesisInput.model_validate(payload, strict=True)


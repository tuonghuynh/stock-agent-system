from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID

import pytest
from pydantic import ValidationError

from stock_agent.domain.models import (
    EvidenceEntry,
    EvidenceSnapshot,
    FreshnessStatus,
    RecommendationAction,
    RecommendationVariant,
    TrustClass,
)
from stock_agent.evaluation import ComparisonEvaluator, VariantOutcome, VersionedCase

DECISION_AT = datetime(2025, 1, 15, 20, tzinfo=UTC)
SNAPSHOT_ID = UUID("40000000-0000-0000-0000-000000000001")


def evidence_snapshot() -> EvidenceSnapshot:
    entry = EvidenceEntry(
        evidence_id=UUID("50000000-0000-0000-0000-000000000001"),
        type="QUOTE",
        content_reference="immutable://quote/aapl",
        source_id="approved-feed",
        source_uri=None,
        publisher="Approved Provider",
        source_timestamp=DECISION_AT - timedelta(minutes=2),
        retrieved_at=DECISION_AT - timedelta(minutes=1),
        content_hash="c" * 64,
        freshness_status=FreshnessStatus.FRESH,
        trust_class=TrustClass.APPROVED_SECONDARY,
    )
    return EvidenceSnapshot(
        snapshot_id=SNAPSHOT_ID,
        run_id=UUID("60000000-0000-0000-0000-000000000001"),
        as_of=DECISION_AT,
        entries=(entry,),
        content_hash="d" * 64,
    )


def outcome(variant: RecommendationVariant, snapshot_hash: str = "d" * 64) -> VariantOutcome:
    return VariantOutcome(
        variant=variant,
        snapshot_id=SNAPSHOT_ID,
        snapshot_hash=snapshot_hash,
        action=RecommendationAction.HOLD,
        confidence=70,
        target_weight=Decimal("5"),
    )


def test_at030_all_variants_use_identical_versioned_snapshot() -> None:
    case = VersionedCase(
        case_id="historical-aapl-2025-01-15",
        decision_at=DECISION_AT,
        snapshot=evidence_snapshot(),
        policy_version="1",
        release_version="release-1",
    )
    outcomes = tuple(outcome(variant) for variant in RecommendationVariant)

    first = ComparisonEvaluator().compare(case, outcomes)
    second = ComparisonEvaluator().compare(case, tuple(reversed(outcomes)))

    assert first == second
    assert first.snapshot_id == SNAPSHOT_ID
    assert tuple(item.variant for item in first.outcomes) == tuple(
        sorted(RecommendationVariant, key=lambda variant: variant.value)
    )
    assert first.actions_agree


def test_at030_mixed_snapshot_is_rejected() -> None:
    case = VersionedCase(
        case_id="historical-aapl",
        decision_at=DECISION_AT,
        snapshot=evidence_snapshot(),
        policy_version="1",
        release_version="release-1",
    )
    outcomes = (
        outcome(RecommendationVariant.RULES_BASELINE),
        outcome(RecommendationVariant.SINGLE_AGENT),
        outcome(RecommendationVariant.MULTI_AGENT, "e" * 64),
    )
    with pytest.raises(ValueError, match="identical case snapshot"):
        ComparisonEvaluator().compare(case, outcomes)


def test_at029_historical_case_rejects_future_snapshot() -> None:
    with pytest.raises(ValidationError, match="newer than historical decision"):
        VersionedCase(
            case_id="future-leak",
            decision_at=DECISION_AT - timedelta(seconds=1),
            snapshot=evidence_snapshot(),
            policy_version="1",
            release_version="release-1",
        )

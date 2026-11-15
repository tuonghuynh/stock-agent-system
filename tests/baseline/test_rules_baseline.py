from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID

import pytest
from pydantic import ValidationError

from stock_agent.baseline import BaselineInput, FundamentalScores, RulesBaseline
from stock_agent.domain.models import (
    EvidenceEntry,
    EvidenceSnapshot,
    FreshnessStatus,
    RecommendationAction,
    RecommendationStatus,
    TrustClass,
)
from stock_agent.evidence.indicators import TechnicalIndicators

AS_OF = datetime(2026, 6, 1, 20, tzinfo=UTC)
RUN_ID = UUID("10000000-0000-0000-0000-000000000001")
SNAPSHOT_ID = UUID("20000000-0000-0000-0000-000000000001")
EVIDENCE_ID = UUID("30000000-0000-0000-0000-000000000001")


def snapshot(freshness: FreshnessStatus = FreshnessStatus.FRESH) -> EvidenceSnapshot:
    entry = EvidenceEntry(
        evidence_id=EVIDENCE_ID,
        type="FUNDAMENTALS",
        content_reference="immutable://fundamentals/aapl/2026-06-01",
        source_id="primary-filing",
        source_uri=None,
        publisher="SEC",
        source_timestamp=AS_OF - timedelta(hours=2),
        retrieved_at=AS_OF - timedelta(hours=1),
        content_hash="a" * 64,
        freshness_status=freshness,
        trust_class=TrustClass.PRIMARY,
    )
    return EvidenceSnapshot(
        snapshot_id=SNAPSHOT_ID,
        run_id=RUN_ID,
        as_of=AS_OF,
        entries=(entry,),
        content_hash="b" * 64,
    )


def baseline_input(
    freshness: FreshnessStatus = FreshnessStatus.FRESH,
    *,
    calculated_at: datetime = AS_OF,
) -> BaselineInput:
    return BaselineInput(
        snapshot=snapshot(freshness),
        policy_version="1",
        release_version="release-1",
        symbol="AAPL",
        horizon="20 trading days",
        current_weight=Decimal("2"),
        current_price=Decimal("200"),
        fundamentals=FundamentalScores(
            quality=Decimal("85"),
            growth=Decimal("80"),
            valuation=Decimal("70"),
            evidence_ids=(EVIDENCE_ID,),
            calculated_at=calculated_at,
        ),
        technicals=TechnicalIndicators(
            as_of=AS_OF,
            latest_bar_at=AS_OF,
            simple_moving_average=Decimal("180"),
            exponential_moving_average=Decimal("190"),
            relative_strength_index=Decimal("60"),
        ),
        next_market_close=AS_OF + timedelta(hours=20),
    )


def test_rec001_five_factor_baseline_is_deterministic() -> None:
    inputs = baseline_input()
    first = RulesBaseline().evaluate(inputs)
    second = RulesBaseline().evaluate(inputs)

    assert first == second
    assert first.recommendation.recommendation_id == second.recommendation.recommendation_id
    assert first.recommendation.action is RecommendationAction.BUY
    assert first.factors.model_dump() == {
        "quality": Decimal("85"),
        "growth": Decimal("80"),
        "valuation": Decimal("70"),
        "trend": Decimal("100"),
        "momentum": Decimal("100"),
        "composite": Decimal("86.25"),
    }
    assert first.snapshot_id == SNAPSHOT_ID
    assert first.policy_version == "1"
    assert first.release_version == "release-1"


@pytest.mark.parametrize(
    "freshness",
    [FreshnessStatus.STALE, FreshnessStatus.UNAVAILABLE, FreshnessStatus.CONFLICTING],
)
def test_materially_unsafe_evidence_yields_wait(
    freshness: FreshnessStatus,
) -> None:
    result = RulesBaseline().evaluate(baseline_input(freshness))
    assert result.recommendation.action is RecommendationAction.WAIT
    assert result.recommendation.status is RecommendationStatus.INELIGIBLE
    assert result.recommendation.target_weight == result.recommendation.current_weight


def test_at029_future_derived_fundamentals_are_rejected() -> None:
    with pytest.raises(ValidationError, match="newer than the evidence snapshot"):
        baseline_input(calculated_at=AS_OF + timedelta(microseconds=1))

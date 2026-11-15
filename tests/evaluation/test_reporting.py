import json
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID

import pytest

from stock_agent.domain.models import (
    EvidenceEntry,
    EvidenceSnapshot,
    FreshnessStatus,
    RecommendationAction,
    RecommendationVariant,
    TrustClass,
)
from stock_agent.evaluation import (
    EvaluatedOutcome,
    EvaluationFailure,
    EvaluationReporter,
    OutcomeMetrics,
    RegressionThresholds,
    VariantOutcome,
    VersionedCase,
)

NOW = datetime(2025, 1, 15, 20, tzinfo=UTC)
SNAPSHOT_ID = UUID("10000000-0000-0000-0000-000000000001")


def case() -> VersionedCase:
    snapshot = EvidenceSnapshot(
        snapshot_id=SNAPSHOT_ID,
        run_id=UUID("20000000-0000-0000-0000-000000000001"),
        as_of=NOW,
        entries=(
            EvidenceEntry(
                evidence_id=UUID("30000000-0000-0000-0000-000000000001"),
                type="QUOTE",
                content_reference="immutable://quote/aapl",
                source_id="approved-feed",
                source_uri=None,
                publisher="Approved Provider",
                source_timestamp=NOW - timedelta(minutes=2),
                retrieved_at=NOW - timedelta(minutes=1),
                content_hash="a" * 64,
                freshness_status=FreshnessStatus.FRESH,
                trust_class=TrustClass.APPROVED_SECONDARY,
            ),
        ),
        content_hash="b" * 64,
    )
    return VersionedCase(
        case_id="aapl-2025-01-15",
        decision_at=NOW,
        snapshot=snapshot,
        policy_version="1",
        release_version="release-1",
    )


def evaluated(
    variant: RecommendationVariant,
    *,
    action: RecommendationAction = RecommendationAction.HOLD,
    risk_violations: int = 0,
    failures: tuple[EvaluationFailure, ...] = (),
) -> EvaluatedOutcome:
    return EvaluatedOutcome(
        outcome=VariantOutcome(
            variant=variant,
            snapshot_id=SNAPSHOT_ID,
            snapshot_hash="b" * 64,
            action=action,
            confidence=70,
            target_weight=Decimal(5),
        ),
        metrics=OutcomeMetrics(
            citation_validity_pct=Decimal(100),
            unsupported_claims=0,
            fresh_evidence_pct=Decimal(100),
            conflicts_detected=1,
            calibration_error=Decimal("0.10"),
            return_pct=Decimal("2.5"),
            drawdown_pct=Decimal("1.25"),
            turnover_pct=Decimal(4),
            latency_ms=100,
            model_calls=0 if variant is RecommendationVariant.RULES_BASELINE else 1,
            tool_calls=1,
            estimated_cost=Decimal("0.01"),
            accepted_risk_violations=risk_violations,
            invalid_outputs=int(EvaluationFailure.MALFORMED_OUTPUT in failures),
        ),
        failures=failures,
    )


def outcomes() -> tuple[EvaluatedOutcome, ...]:
    return tuple(evaluated(variant) for variant in RecommendationVariant)


def test_at030_all_report_variants_share_identical_snapshot() -> None:
    mixed = list(outcomes())
    mixed[-1] = mixed[-1].model_copy(
        update={"outcome": mixed[-1].outcome.model_copy(update={"snapshot_hash": "c" * 64})}
    )
    with pytest.raises(ValueError, match="identical case snapshot"):
        EvaluationReporter().build(cases=(case(),), outcomes=tuple(mixed))


def test_at031_at032_report_is_deterministic_complete_and_zero_risk() -> None:
    reporter = EvaluationReporter()
    first = reporter.build(cases=(case(),), outcomes=outcomes())
    second = reporter.build(cases=(case(),), outcomes=tuple(reversed(outcomes())))
    assert first == second and first.accepted_risk_violations == 0
    assert len(first.variants) == 3
    assert all(
        item.latency_ms == 100 and item.estimated_cost == Decimal("0.01") for item in first.variants
    )
    assert all(item.citation_validity_pct == Decimal("100.0000") for item in first.variants)
    assert json.loads(reporter.render_json(first))["fingerprint"] == first.fingerprint
    human = reporter.render_markdown(first)
    assert "Accepted risk violations: **0**" in human
    assert all(variant.value in human for variant in RecommendationVariant)


def test_at032_any_accepted_risk_violation_fails_report() -> None:
    unsafe = tuple(
        evaluated(variant, risk_violations=int(variant is RecommendationVariant.MULTI_AGENT))
        for variant in RecommendationVariant
    )
    with pytest.raises(ValueError, match="must equal zero"):
        EvaluationReporter().build(cases=(case(),), outcomes=unsafe)


def test_eva005_failure_taxonomy_and_abstentions_are_counted() -> None:
    classified = (
        evaluated(RecommendationVariant.RULES_BASELINE),
        evaluated(
            RecommendationVariant.SINGLE_AGENT,
            action=RecommendationAction.WAIT,
            failures=(EvaluationFailure.MALFORMED_OUTPUT, EvaluationFailure.PROMPT_INJECTION),
        ),
        evaluated(
            RecommendationVariant.MULTI_AGENT,
            action=RecommendationAction.NEEDS_REVIEW,
            failures=(
                EvaluationFailure.STALE_DATA,
                EvaluationFailure.CONFLICTING_SOURCES,
                EvaluationFailure.BROKER_FAILURE,
            ),
        ),
    )
    report = EvaluationReporter().build(cases=(case(),), outcomes=classified)
    single = next(
        item for item in report.variants if item.variant is RecommendationVariant.SINGLE_AGENT
    )
    multi = next(
        item for item in report.variants if item.variant is RecommendationVariant.MULTI_AGENT
    )
    assert single.abstentions == 1 and single.invalid_outputs == 1
    assert single.failures[EvaluationFailure.PROMPT_INJECTION] == 1
    assert multi.needs_review == 1
    assert all(
        multi.failures[kind] == 1
        for kind in (
            EvaluationFailure.STALE_DATA,
            EvaluationFailure.CONFLICTING_SOURCES,
            EvaluationFailure.BROKER_FAILURE,
        )
    )


def test_regression_gate_is_stable_and_names_failures() -> None:
    report = EvaluationReporter().build(cases=(case(),), outcomes=outcomes())
    passing = RegressionThresholds(
        minimum_citation_validity_pct=Decimal(99),
        maximum_unsupported_claims=0,
        maximum_calibration_error=Decimal("0.2"),
        maximum_drawdown_pct=Decimal(2),
        maximum_latency_ms=100,
        maximum_estimated_cost=Decimal("0.02"),
    )
    assert EvaluationReporter.regression_gate(report, passing).passed
    decision = EvaluationReporter.regression_gate(
        report, passing.model_copy(update={"maximum_latency_ms": 99})
    )
    assert not decision.passed
    assert decision.violations == tuple(
        sorted(f"{variant.value}:LATENCY" for variant in RecommendationVariant)
    )

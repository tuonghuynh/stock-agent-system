from stock_agent.domain.models import RecommendationVariant
from stock_agent.evaluation.models import ComparisonReport, VariantOutcome, VersionedCase

_REQUIRED_VARIANTS = frozenset(RecommendationVariant)


class ComparisonEvaluator:
    """Compare variants only when they used one identical versioned case snapshot."""

    def compare(
        self, case: VersionedCase, outcomes: tuple[VariantOutcome, ...]
    ) -> ComparisonReport:
        if len(outcomes) != len(_REQUIRED_VARIANTS):
            raise ValueError("exactly one outcome for every recommendation variant is required")
        if {outcome.variant for outcome in outcomes} != _REQUIRED_VARIANTS:
            raise ValueError("rules, single-agent, and multi-agent outcomes are required")
        for outcome in outcomes:
            if (
                outcome.snapshot_id != case.snapshot.snapshot_id
                or outcome.snapshot_hash != case.snapshot.content_hash
            ):
                raise ValueError("all variants must use the identical case snapshot")
        ordered = tuple(sorted(outcomes, key=lambda outcome: outcome.variant.value))
        return ComparisonReport(
            case_id=case.case_id,
            snapshot_id=case.snapshot.snapshot_id,
            snapshot_hash=case.snapshot.content_hash,
            policy_version=case.policy_version,
            release_version=case.release_version,
            outcomes=ordered,
            actions_agree=len({outcome.action for outcome in ordered}) == 1,
        )

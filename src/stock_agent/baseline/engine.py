import hashlib
import json
from datetime import timedelta
from decimal import ROUND_HALF_UP, Decimal
from uuid import UUID, uuid5

from stock_agent.baseline.models import BaselineInput, BaselineResult, FactorScores
from stock_agent.domain.models import (
    FreshnessStatus,
    Recommendation,
    RecommendationAction,
    RecommendationStatus,
    RecommendationVariant,
)

_SCORE_QUANTUM = Decimal("0.01")
_IDENTITY_NAMESPACE = UUID("69a20af0-5060-4b56-915d-2b75d5dcb596")


class RulesBaseline:
    """Pure quality/growth/valuation/trend/momentum recommendation rules."""

    def evaluate(self, inputs: BaselineInput) -> BaselineResult:
        factors = self._score(inputs)
        unsafe_entries = tuple(
            entry
            for entry in inputs.snapshot.entries
            if entry.freshness_status is not FreshnessStatus.FRESH
        )
        if unsafe_entries:
            action = RecommendationAction.WAIT
            status = RecommendationStatus.INELIGIBLE
            reason = "Material evidence is stale, unavailable, or conflicting"
        else:
            action = self._action(factors.composite)
            status = RecommendationStatus.PROPOSED
            reason = f"Deterministic five-factor composite is {factors.composite}"

        target = self._target_weight(inputs.current_weight, action)
        identity = self._identity(inputs, factors, action)
        expires_at = min(inputs.snapshot.as_of + timedelta(hours=24), inputs.next_market_close)
        evidence_ids = tuple(sorted(inputs.fundamentals.evidence_ids, key=lambda item: item.hex))
        recommendation = Recommendation(
            recommendation_id=uuid5(_IDENTITY_NAMESPACE, identity),
            run_id=inputs.snapshot.run_id,
            variant=RecommendationVariant.RULES_BASELINE,
            symbol=inputs.symbol,
            action=action,
            thesis=reason,
            bull_case="High five-factor score supports upside if current evidence persists",
            base_case="Five-factor conditions remain near their current deterministic scores",
            bear_case="Fundamental or technical factors weaken after the snapshot",
            supporting_evidence_ids=evidence_ids,
            contradicting_evidence_ids=tuple(entry.evidence_id for entry in unsafe_entries),
            material_conflicts=tuple(
                conflict for entry in unsafe_entries for conflict in entry.conflicts
            ),
            invalidation_conditions=("A material factor changes after the snapshot",),
            horizon=inputs.horizon,
            confidence=int(factors.composite),
            current_weight=inputs.current_weight,
            target_weight=target,
            entry_conditions=("All deterministic policy and risk gates pass",),
            exit_conditions=("Baseline composite falls below the hold threshold",),
            expires_at=expires_at,
            status=status,
        )
        return BaselineResult(
            recommendation=recommendation,
            snapshot_id=inputs.snapshot.snapshot_id,
            snapshot_hash=inputs.snapshot.content_hash,
            policy_version=inputs.policy_version,
            release_version=inputs.release_version,
            factors=factors,
        )

    @staticmethod
    def _score(inputs: BaselineInput) -> FactorScores:
        technicals = inputs.technicals
        if (
            technicals.simple_moving_average is None
            or technicals.exponential_moving_average is None
        ):
            trend = Decimal(0)
        else:
            above = sum(
                inputs.current_price >= average
                for average in (
                    technicals.simple_moving_average,
                    technicals.exponential_moving_average,
                )
            )
            trend = (Decimal(0), Decimal(50), Decimal(100))[above]
        rsi = technicals.relative_strength_index
        if rsi is None:
            momentum = Decimal(0)
        elif Decimal(45) <= rsi <= Decimal(70):
            momentum = Decimal(100)
        elif Decimal(30) <= rsi < Decimal(45) or Decimal(70) < rsi <= Decimal(80):
            momentum = Decimal(60)
        else:
            momentum = Decimal(20)
        fundamentals = inputs.fundamentals
        composite = (
            fundamentals.quality * Decimal("0.25")
            + fundamentals.growth * Decimal("0.20")
            + fundamentals.valuation * Decimal("0.20")
            + trend * Decimal("0.20")
            + momentum * Decimal("0.15")
        ).quantize(_SCORE_QUANTUM, rounding=ROUND_HALF_UP)
        return FactorScores(
            quality=fundamentals.quality,
            growth=fundamentals.growth,
            valuation=fundamentals.valuation,
            trend=trend,
            momentum=momentum,
            composite=composite,
        )

    @staticmethod
    def _action(score: Decimal) -> RecommendationAction:
        if score >= Decimal(65):
            return RecommendationAction.BUY
        if score < Decimal(40):
            return RecommendationAction.SELL
        return RecommendationAction.HOLD

    @staticmethod
    def _target_weight(current: Decimal, action: RecommendationAction) -> Decimal:
        if action is RecommendationAction.BUY:
            return min(current + Decimal(2), Decimal(100))
        if action is RecommendationAction.SELL:
            return max(current - Decimal(2), Decimal(0))
        return current

    @staticmethod
    def _identity(
        inputs: BaselineInput, factors: FactorScores, action: RecommendationAction
    ) -> str:
        canonical = {
            "action": action.value,
            "factors": factors.model_dump(mode="json"),
            "horizon": inputs.horizon,
            "policy_version": inputs.policy_version,
            "release_version": inputs.release_version,
            "snapshot_hash": inputs.snapshot.content_hash,
            "symbol": inputs.symbol,
        }
        return hashlib.sha256(
            json.dumps(canonical, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()

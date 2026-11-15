"""Deterministic synthesis of research and critique into a proposal."""

import hashlib
import json
from datetime import timedelta
from uuid import UUID, uuid5

from stock_agent.agents.portfolio.models import (
    CriticDisposition,
    PortfolioSynthesisInput,
    PortfolioSynthesisResult,
)
from stock_agent.domain.models import (
    Recommendation,
    RecommendationAction,
    RecommendationStatus,
    RecommendationVariant,
)

_IDENTITY_NAMESPACE = UUID("5cafae29-3dab-4af5-a882-bf197e505c72")
_MINIMUM_EXECUTABLE_CONFIDENCE = 65


class PortfolioSynthesizer:
    """Produces a recommendation proposal; deterministic risk remains authoritative."""

    def synthesize(self, inputs: PortfolioSynthesisInput) -> PortfolioSynthesisResult:
        draft = inputs.draft
        contradictory_overlap = set(draft.supporting_evidence_ids) & set(
            draft.contradicting_evidence_ids
        )
        overlap_conflicts = tuple(
            f"Evidence {evidence_id} is both supporting and contradicting"
            for evidence_id in sorted(contradictory_overlap, key=lambda item: item.hex)
        )
        conflicts = tuple(
            dict.fromkeys(
                (
                    *draft.material_conflicts,
                    *inputs.critique.unresolved_material_conflicts,
                    *overlap_conflicts,
                )
            )
        )
        if not inputs.material_data_complete:
            action = RecommendationAction.WAIT
            status = RecommendationStatus.INELIGIBLE
            reason = "Material data is incomplete"
        elif conflicts or inputs.critique.disposition in {
            CriticDisposition.REJECTED,
            CriticDisposition.NEEDS_REVIEW,
            CriticDisposition.REVISE,
        }:
            action = RecommendationAction.NEEDS_REVIEW
            status = RecommendationStatus.INELIGIBLE
            reason = "Independent critique has unresolved material objections"
        elif draft.confidence < _MINIMUM_EXECUTABLE_CONFIDENCE:
            action = RecommendationAction.WAIT
            status = RecommendationStatus.INELIGIBLE
            reason = "Confidence is below the executable threshold"
        else:
            action = draft.action
            status = RecommendationStatus.PROPOSED
            reason = draft.thesis

        target_weight = (
            inputs.current_weight
            if action in {RecommendationAction.WAIT, RecommendationAction.NEEDS_REVIEW}
            else draft.target_weight
        )
        identity = self._identity(inputs, action, conflicts)
        recommendation = Recommendation(
            recommendation_id=uuid5(_IDENTITY_NAMESPACE, identity),
            run_id=inputs.run_id,
            variant=RecommendationVariant.MULTI_AGENT,
            symbol=inputs.symbol,
            action=action,
            thesis=reason,
            bull_case=draft.bull_case,
            base_case=draft.base_case,
            bear_case=draft.bear_case,
            supporting_evidence_ids=draft.supporting_evidence_ids,
            contradicting_evidence_ids=draft.contradicting_evidence_ids,
            material_conflicts=conflicts,
            invalidation_conditions=draft.invalidation_conditions,
            horizon=inputs.horizon,
            confidence=draft.confidence,
            current_weight=inputs.current_weight,
            target_weight=target_weight,
            entry_conditions=draft.entry_conditions,
            exit_conditions=draft.exit_conditions,
            expires_at=min(inputs.as_of + timedelta(hours=24), inputs.next_market_close),
            status=status,
        )
        return PortfolioSynthesisResult(
            recommendation=recommendation,
            snapshot_id=inputs.snapshot_id,
            snapshot_hash=inputs.snapshot_hash,
            policy_version=inputs.policy_version,
            release_version=inputs.release_version,
            workflow_version=inputs.workflow_version,
            model_version=inputs.model_version,
            prompt_version=inputs.prompt_version,
        )

    @staticmethod
    def _identity(
        inputs: PortfolioSynthesisInput,
        action: RecommendationAction,
        conflicts: tuple[str, ...],
    ) -> str:
        canonical = {
            "action": action.value,
            "conflicts": conflicts,
            "draft": inputs.draft.model_dump(mode="json"),
            "policy_version": inputs.policy_version,
            "release_version": inputs.release_version,
            "run_id": str(inputs.run_id),
            "snapshot_hash": inputs.snapshot_hash,
            "workflow_version": inputs.workflow_version,
        }
        return hashlib.sha256(
            json.dumps(canonical, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()


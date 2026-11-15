"""Deterministic independent challenge of candidate recommendations."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable
from uuid import UUID

from stock_agent.agents.critic.models import (
    CriticInput,
    CriticResult,
    CritiqueDisposition,
    Materiality,
    Objection,
    ObjectionKind,
)


class DeterministicCritic:
    """Finds bounded material flaws without proposing or authorizing an order."""

    minimum_confidence = 65

    def review(self, review: CriticInput) -> CriticResult:
        objections = list(self._objections(review))[: review.maximum_objections]
        unresolved_material = tuple(
            item.summary
            for item in objections
            if item.materiality is Materiality.MATERIAL and not item.resolved
        )
        disposition = self._disposition(objections)
        return CriticResult(
            run_id=review.run_id,
            candidate_recommendation_id=review.candidate.recommendation_id,
            candidate_fingerprint=self._fingerprint(review),
            disposition=disposition,
            objections=tuple(objections),
            unresolved_material_conflicts=unresolved_material,
            blocks_intent=disposition is not CritiqueDisposition.CLEAR,
        )

    def _objections(self, review: CriticInput) -> Iterable[Objection]:
        sequence = 0

        def objection(
            kind: ObjectionKind,
            materiality: Materiality,
            summary: str,
            evidence_ids: tuple[UUID, ...] = (),
        ) -> Objection:
            nonlocal sequence
            sequence += 1
            return Objection(
                objection_id=f"OBJ-{sequence:03d}",
                kind=kind,
                materiality=materiality,
                summary=summary,
                evidence_ids=evidence_ids,
                resolved=False,
            )

        candidate = review.candidate
        supported_by_findings = {
            evidence_id
            for finding in review.findings
            for evidence_id in (*finding.evidence_ids, *finding.supporting_evidence)
        }
        unsupported = tuple(
            sorted(set(candidate.supporting_evidence_ids) - supported_by_findings, key=str)
        )
        if not candidate.supporting_evidence_ids or unsupported:
            yield objection(
                ObjectionKind.UNSUPPORTED_CLAIM,
                Materiality.MATERIAL,
                "Candidate thesis lacks finding-level evidence support",
                unsupported,
            )

        contradicted = {
            evidence_id
            for finding in review.findings
            for evidence_id in finding.contradicting_evidence
        }
        overlap = tuple(
            sorted(
                set(candidate.supporting_evidence_ids)
                & (set(candidate.contradicting_evidence_ids) | contradicted),
                key=str,
            )
        )
        if overlap:
            yield objection(
                ObjectionKind.CONTRADICTION,
                Materiality.MATERIAL,
                "Candidate relies on evidence that is also contradicted",
                overlap,
            )

        for conflict in candidate.material_conflicts:
            yield objection(
                ObjectionKind.MATERIAL_CONFLICT,
                Materiality.MATERIAL,
                f"Unresolved material conflict: {conflict}",
            )

        if candidate.confidence < self.minimum_confidence:
            yield objection(
                ObjectionKind.LOW_CONFIDENCE,
                Materiality.MATERIAL,
                f"Confidence {candidate.confidence} is below {self.minimum_confidence}",
            )

        if candidate.target_weight > review.maximum_target_weight:
            yield objection(
                ObjectionKind.CONCENTRATION,
                Materiality.MATERIAL,
                "Target weight exceeds the frozen critic concentration boundary",
            )

        if candidate.expires_at <= review.as_of:
            yield objection(
                ObjectionKind.EXPIRED,
                Materiality.MATERIAL,
                "Candidate is already expired at the review timestamp",
            )

        uncertain_findings = tuple(
            finding
            for finding in review.findings
            if finding.missing_information or finding.assumptions
        )
        if any(finding.missing_information for finding in uncertain_findings):
            yield objection(
                ObjectionKind.UNCERTAINTY,
                Materiality.MATERIAL,
                "Material source findings report missing information",
                tuple(
                    sorted(
                        {
                            evidence_id
                            for finding in uncertain_findings
                            for evidence_id in finding.evidence_ids
                        },
                        key=str,
                    )
                ),
            )
        elif uncertain_findings:
            yield objection(
                ObjectionKind.UNCERTAINTY,
                Materiality.NON_MATERIAL,
                "Source findings contain disclosed assumptions",
                tuple(
                    sorted(
                        {
                            evidence_id
                            for finding in uncertain_findings
                            for evidence_id in finding.evidence_ids
                        },
                        key=str,
                    )
                ),
            )

        if not candidate.bear_case.strip() or not candidate.invalidation_conditions:
            yield objection(
                ObjectionKind.DOWNSIDE,
                Materiality.MATERIAL,
                "Candidate lacks a usable downside or invalidation case",
            )

    @staticmethod
    def _disposition(objections: list[Objection]) -> CritiqueDisposition:
        material = [
            item
            for item in objections
            if item.materiality is Materiality.MATERIAL and not item.resolved
        ]
        if not material:
            return CritiqueDisposition.CLEAR
        if any(item.kind is ObjectionKind.LOW_CONFIDENCE for item in material):
            return CritiqueDisposition.WAIT
        if any(
            item.kind in {ObjectionKind.CONTRADICTION, ObjectionKind.MATERIAL_CONFLICT}
            for item in material
        ):
            return CritiqueDisposition.NEEDS_REVIEW
        return CritiqueDisposition.REVISE

    @staticmethod
    def _fingerprint(review: CriticInput) -> str:
        canonical = {
            "candidate": review.candidate.model_dump(mode="json"),
            "findings": [item.model_dump(mode="json") for item in review.findings],
            "run_id": str(review.run_id),
        }
        return hashlib.sha256(
            json.dumps(canonical, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()

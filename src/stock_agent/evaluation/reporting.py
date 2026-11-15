"""Deterministic evaluation aggregation, reporting and regression gates."""

from __future__ import annotations

import hashlib
import json
from collections import Counter, defaultdict
from decimal import ROUND_HALF_UP, Decimal

from stock_agent.domain.models import RecommendationAction, RecommendationVariant
from stock_agent.evaluation.models import (
    EvaluatedOutcome,
    EvaluationFailure,
    EvaluationReport,
    RegressionDecision,
    RegressionThresholds,
    VariantAggregate,
    VersionedCase,
)

_REQUIRED_VARIANTS = frozenset(RecommendationVariant)
_QUANTUM = Decimal("0.0001")


class EvaluationReporter:
    def build(
        self,
        *,
        cases: tuple[VersionedCase, ...],
        outcomes: tuple[EvaluatedOutcome, ...],
        schema_version: str = "evaluation-report-v1",
    ) -> EvaluationReport:
        if not cases:
            raise ValueError("evaluation requires at least one versioned case")
        ordered_cases = tuple(sorted(cases, key=lambda case: case.case_id))
        if len({case.case_id for case in ordered_cases}) != len(ordered_cases):
            raise ValueError("case IDs must be unique")
        releases = {case.release_version for case in ordered_cases}
        policies = {case.policy_version for case in ordered_cases}
        if len(releases) != 1 or len(policies) != 1:
            raise ValueError("one report requires one release and policy version")
        if len(outcomes) != len(ordered_cases) * len(_REQUIRED_VARIANTS):
            raise ValueError("every case requires exactly one outcome per variant")

        grouped: dict[RecommendationVariant, list[EvaluatedOutcome]] = defaultdict(list)
        remaining = list(outcomes)
        for case in ordered_cases:
            matches = [
                item
                for item in remaining
                if item.outcome.snapshot_id == case.snapshot.snapshot_id
                and item.outcome.snapshot_hash == case.snapshot.content_hash
            ]
            matched_variants = {item.outcome.variant for item in matches}
            if len(matches) != 3 or matched_variants != _REQUIRED_VARIANTS:
                raise ValueError("all variants must use each identical case snapshot exactly once")
            for item in matches:
                grouped[item.outcome.variant].append(item)
                remaining.remove(item)
        if remaining:
            raise ValueError("outcome references a snapshot outside the versioned cases")

        aggregates = tuple(
            self._aggregate(variant, tuple(grouped[variant]))
            for variant in sorted(_REQUIRED_VARIANTS, key=lambda item: item.value)
        )
        violations = sum(item.accepted_risk_violations for item in aggregates)
        if violations:
            raise ValueError("accepted deterministic risk violations must equal zero")
        release = next(iter(releases))
        policy = next(iter(policies))
        canonical = {
            "case_ids": [case.case_id for case in ordered_cases],
            "policy_version": policy,
            "release_version": release,
            "schema_version": schema_version,
            "snapshot_hashes": [case.snapshot.content_hash for case in ordered_cases],
            "variants": [item.model_dump(mode="json") for item in aggregates],
        }
        fingerprint = hashlib.sha256(
            json.dumps(canonical, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        return EvaluationReport(
            schema_version=schema_version,
            release_version=release,
            policy_version=policy,
            case_ids=tuple(case.case_id for case in ordered_cases),
            snapshot_hashes=tuple(case.snapshot.content_hash for case in ordered_cases),
            variants=aggregates,
            accepted_risk_violations=0,
            fingerprint=fingerprint,
        )

    @staticmethod
    def _aggregate(
        variant: RecommendationVariant, outcomes: tuple[EvaluatedOutcome, ...]
    ) -> VariantAggregate:
        count = Decimal(len(outcomes))

        def mean(values: tuple[Decimal, ...]) -> Decimal:
            return (sum(values, start=Decimal(0)) / count).quantize(
                _QUANTUM, rounding=ROUND_HALF_UP
            )

        failure_counts: Counter[EvaluationFailure] = Counter(
            failure for item in outcomes for failure in item.failures
        )
        return VariantAggregate(
            variant=variant,
            case_count=len(outcomes),
            citation_validity_pct=mean(
                tuple(item.metrics.citation_validity_pct for item in outcomes)
            ),
            unsupported_claims=sum(item.metrics.unsupported_claims for item in outcomes),
            fresh_evidence_pct=mean(tuple(item.metrics.fresh_evidence_pct for item in outcomes)),
            conflicts_detected=sum(item.metrics.conflicts_detected for item in outcomes),
            calibration_error=mean(tuple(item.metrics.calibration_error for item in outcomes)),
            return_pct=mean(tuple(item.metrics.return_pct for item in outcomes)),
            maximum_drawdown_pct=max(item.metrics.drawdown_pct for item in outcomes),
            turnover_pct=mean(tuple(item.metrics.turnover_pct for item in outcomes)),
            latency_ms=sum(item.metrics.latency_ms for item in outcomes),
            model_calls=sum(item.metrics.model_calls for item in outcomes),
            tool_calls=sum(item.metrics.tool_calls for item in outcomes),
            estimated_cost=sum((item.metrics.estimated_cost for item in outcomes), Decimal(0)),
            accepted_risk_violations=sum(
                item.metrics.accepted_risk_violations for item in outcomes
            ),
            abstentions=sum(item.outcome.action is RecommendationAction.WAIT for item in outcomes),
            needs_review=sum(
                item.outcome.action is RecommendationAction.NEEDS_REVIEW for item in outcomes
            ),
            invalid_outputs=sum(item.metrics.invalid_outputs for item in outcomes),
            failures={failure: failure_counts[failure] for failure in EvaluationFailure},
        )

    @staticmethod
    def render_json(report: EvaluationReport) -> str:
        return report.model_dump_json(indent=2)

    @staticmethod
    def render_markdown(report: EvaluationReport) -> str:
        lines = [
            "# Evaluation Comparison Report",
            "",
            f"- Release: `{report.release_version}`",
            f"- Policy: `{report.policy_version}`",
            f"- Schema: `{report.schema_version}`",
            f"- Fingerprint: `{report.fingerprint}`",
            f"- Accepted risk violations: **{report.accepted_risk_violations}**",
            "",
            "| Variant | Cases | Citation % | Unsupported | Return % | Drawdown % | "
            "Latency ms | Cost | WAIT | Review | Invalid |",
            "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
        ]
        for item in report.variants:
            fields = (
                item.variant.value,
                str(item.case_count),
                str(item.citation_validity_pct),
                str(item.unsupported_claims),
                str(item.return_pct),
                str(item.maximum_drawdown_pct),
                str(item.latency_ms),
                str(item.estimated_cost),
                str(item.abstentions),
                str(item.needs_review),
                str(item.invalid_outputs),
            )
            lines.append("| " + " | ".join(fields) + " |")
        return "\n".join(lines) + "\n"

    @staticmethod
    def regression_gate(
        report: EvaluationReport, thresholds: RegressionThresholds
    ) -> RegressionDecision:
        violations: list[str] = []
        for item in report.variants:
            prefix = item.variant.value
            if item.citation_validity_pct < thresholds.minimum_citation_validity_pct:
                violations.append(f"{prefix}:CITATION_VALIDITY")
            if item.unsupported_claims > thresholds.maximum_unsupported_claims:
                violations.append(f"{prefix}:UNSUPPORTED_CLAIMS")
            if item.calibration_error > thresholds.maximum_calibration_error:
                violations.append(f"{prefix}:CALIBRATION")
            if item.maximum_drawdown_pct > thresholds.maximum_drawdown_pct:
                violations.append(f"{prefix}:DRAWDOWN")
            if item.latency_ms > thresholds.maximum_latency_ms:
                violations.append(f"{prefix}:LATENCY")
            if item.estimated_cost > thresholds.maximum_estimated_cost:
                violations.append(f"{prefix}:COST")
        if report.accepted_risk_violations:
            violations.append("GLOBAL:RISK_VIOLATIONS")
        return RegressionDecision(passed=not violations, violations=tuple(sorted(violations)))

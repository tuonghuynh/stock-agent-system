"""Schema-first, budgeted and fail-safe model gateway."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from datetime import datetime, timedelta
from decimal import Decimal
from uuid import UUID, uuid5

from pydantic import ValidationError

from stock_agent.domain.models import (
    AgentFinding,
    AgentRole,
    FindingClassification,
    Recommendation,
    RecommendationAction,
    RecommendationStatus,
    RecommendationVariant,
)
from stock_agent.model_gateway.models import (
    FrozenModelContext,
    GatewayResult,
    GatewayStatus,
    ModelBudget,
    ModelCall,
    SingleAgentDraft,
)
from stock_agent.model_gateway.provider import ModelProvider

_IDENTITY_NAMESPACE = UUID("1e41f98a-984c-4b2b-a850-279493220c3a")
_FORBIDDEN_TOOLS = frozenset(
    {"broker", "submit_order", "cancel_order", "credentials", "policy_write", "workflow_write"}
)


class ModelGateway:
    def __init__(self, provider: ModelProvider, now: Callable[[], datetime]) -> None:
        self._provider = provider
        self._now = now

    def single_agent(
        self,
        *,
        context: FrozenModelContext,
        budget: ModelBudget,
        current_weight: Decimal,
        next_market_close: datetime,
    ) -> GatewayResult:
        self._validate_context(context)
        errors: list[str] = []
        tokens = 0
        cost = Decimal(0)
        calls = 0
        schema = SingleAgentDraft.model_json_schema()
        attempts = min(budget.max_calls, 2)

        for attempt in range(attempts):
            if self._now() >= budget.deadline:
                errors.append("DEADLINE_EXCEEDED")
                break
            response = self._provider.complete(
                ModelCall(
                    context=context,
                    output_schema=schema,
                    repair=attempt == 1,
                    validation_error_code=errors[-1] if attempt == 1 else None,
                )
            )
            calls += 1
            tokens += response.token_count
            cost += response.estimated_cost
            if (
                response.completed_at > budget.deadline
                or tokens > budget.max_tokens
                or cost > budget.max_cost
            ):
                errors.append("BUDGET_EXCEEDED")
                break
            try:
                draft = SingleAgentDraft.model_validate_json(response.content, strict=True)
                self._validate_draft(draft, context)
            except (ValidationError, ValueError):
                errors.append("SCHEMA_OR_AUTHORITY_VIOLATION")
                continue
            return self._validated_result(
                draft=draft,
                context=context,
                current_weight=current_weight,
                next_market_close=next_market_close,
                calls=calls,
                tokens=tokens,
                cost=cost,
            )
        return GatewayResult(
            status=GatewayStatus.SAFE_FAILURE,
            action=RecommendationAction.WAIT,
            calls_used=calls,
            tokens_used=tokens,
            cost_used=cost,
            error_codes=tuple(errors) or ("MODEL_UNAVAILABLE",),
        )

    @staticmethod
    def _validate_context(context: FrozenModelContext) -> None:
        names: set[str] = set()
        for tool in context.allowed_tools:
            if not tool.read_only:
                raise ValueError("model tools must be read-only")
            if tool.name in _FORBIDDEN_TOOLS or tool.name in names:
                raise ValueError("model tool is forbidden or duplicated")
            names.add(tool.name)
        if len(context.evidence_ids) != len(set(context.evidence_ids)):
            raise ValueError("evidence IDs must be unique")
        if len(context.evidence_references) != len(context.evidence_ids):
            raise ValueError("every evidence ID requires one opaque reference")

    @staticmethod
    def _validate_draft(draft: SingleAgentDraft, context: FrozenModelContext) -> None:
        if draft.symbol != context.symbol or draft.horizon != context.horizon:
            raise ValueError("model cannot change symbol or horizon")
        available = set(context.evidence_ids)
        referenced = set(draft.supporting_evidence_ids) | set(draft.contradicting_evidence_ids)
        if not referenced.issubset(available):
            raise ValueError("recommendation references evidence outside the frozen snapshot")
        allowed_tools = {tool.name for tool in context.allowed_tools}
        for call in draft.tool_calls:
            if call.name not in allowed_tools:
                raise ValueError("model requested an unauthorized tool")
            if any(key.lower() in {"secret", "token", "credential", "account_id"}
                   for key in call.arguments):
                raise ValueError("model requested sensitive tool parameters")
        for finding in draft.findings:
            if finding.analysis_timestamp != context.as_of:
                raise ValueError("finding timestamp must equal the frozen snapshot time")
            finding_evidence = (
                set(finding.evidence_ids)
                | set(finding.supporting_evidence)
                | set(finding.contradicting_evidence)
            )
            if not finding_evidence.issubset(available):
                raise ValueError("finding references evidence outside the frozen snapshot")

    @staticmethod
    def _validated_result(
        *,
        draft: SingleAgentDraft,
        context: FrozenModelContext,
        current_weight: Decimal,
        next_market_close: datetime,
        calls: int,
        tokens: int,
        cost: Decimal,
    ) -> GatewayResult:
        identity = hashlib.sha256(
            json.dumps(
                {
                    "context": context.model_dump(mode="json"),
                    "draft": draft.model_dump(mode="json"),
                },
                sort_keys=True,
                separators=(",", ":"),
            ).encode()
        ).hexdigest()
        recommendation_id = uuid5(_IDENTITY_NAMESPACE, f"recommendation:{identity}")
        findings = tuple(
            AgentFinding(
                finding_id=uuid5(_IDENTITY_NAMESPACE, f"finding:{identity}:{index}"),
                agent_role=AgentRole.SINGLE_AGENT,
                run_id=context.run_id,
                claim=finding.claim,
                classification=FindingClassification(finding.classification),
                evidence_ids=finding.evidence_ids,
                supporting_evidence=finding.supporting_evidence,
                contradicting_evidence=finding.contradicting_evidence,
                confidence=finding.confidence,
                assumptions=finding.assumptions,
                missing_information=finding.missing_information,
                analysis_timestamp=finding.analysis_timestamp,
                model_version=context.model_version,
                prompt_version=context.prompt_version,
            )
            for index, finding in enumerate(draft.findings)
        )
        expires_at = min(context.as_of + timedelta(hours=24), next_market_close)
        recommendation = Recommendation(
            recommendation_id=recommendation_id,
            run_id=context.run_id,
            variant=RecommendationVariant.SINGLE_AGENT,
            symbol=context.symbol,
            action=draft.action,
            thesis=draft.thesis,
            bull_case=draft.bull_case,
            base_case=draft.base_case,
            bear_case=draft.bear_case,
            supporting_evidence_ids=draft.supporting_evidence_ids,
            contradicting_evidence_ids=draft.contradicting_evidence_ids,
            material_conflicts=draft.material_conflicts,
            invalidation_conditions=draft.invalidation_conditions,
            horizon=context.horizon,
            confidence=draft.confidence,
            current_weight=current_weight,
            target_weight=draft.target_weight,
            entry_conditions=draft.entry_conditions,
            exit_conditions=draft.exit_conditions,
            expires_at=expires_at,
            status=RecommendationStatus.PROPOSED,
        )
        return GatewayResult(
            status=GatewayStatus.VALIDATED,
            action=draft.action,
            recommendation=recommendation,
            findings=findings,
            calls_used=calls,
            tokens_used=tokens,
            cost_used=cost,
        )


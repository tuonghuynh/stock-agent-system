from collections.abc import Callable
from datetime import datetime
from typing import Protocol

from stock_agent.coordinator.models import (
    BudgetUsage,
    Checkpoint,
    CriticDisposition,
    RunOutcome,
    RunRecord,
    Step,
    StepResult,
    WorkflowResult,
)
from stock_agent.coordinator.store import InMemoryRunStore
from stock_agent.domain.models import RunManifest


class WorkflowPorts(Protocol):
    def evidence(self, manifest: RunManifest) -> StepResult: ...
    def research(self, manifest: RunManifest, evidence: StepResult) -> StepResult: ...
    def portfolio(
        self, manifest: RunManifest, research: StepResult, critique: StepResult | None
    ) -> StepResult: ...
    def critic(self, manifest: RunManifest, candidate: StepResult) -> StepResult: ...
    def risk(self, manifest: RunManifest, candidate: StepResult) -> StepResult: ...
    def execute(self, manifest: RunManifest, candidate: StepResult) -> StepResult: ...


class Coordinator:
    def __init__(
        self, store: InMemoryRunStore, ports: WorkflowPorts, now: Callable[[], datetime]
    ) -> None:
        self._store = store
        self._ports = ports
        self._now = now

    def run(self, manifest: RunManifest) -> WorkflowResult:
        record = self._store.create_or_get(manifest)
        if record.outcome is RunOutcome.FAILED and record.failure_code == "STEP_FAILURE":
            record = self._store.resume_step_failure(manifest.run_id)
        if record.outcome is not RunOutcome.RUNNING:
            return self._result(record)
        try:
            record = self._run(record)
        except Exception:
            persisted = self._store.get(manifest.run_id)
            if persisted is not None:
                record = persisted
            record = self._terminal(record, RunOutcome.FAILED, "STEP_FAILURE")
        return self._result(record)

    def _run(self, record: RunRecord) -> RunRecord:
        manifest = record.manifest
        evidence, record = self._step(record, Step.EVIDENCE, lambda: self._ports.evidence(manifest))
        if evidence.outcome is not RunOutcome.RUNNING:
            return self._terminal(record, evidence.outcome)
        research, record = self._step(
            record, Step.RESEARCH, lambda: self._ports.research(manifest, evidence)
        )
        if research.outcome is not RunOutcome.RUNNING:
            return self._terminal(record, research.outcome)
        candidate, record = self._step(
            record, Step.PORTFOLIO, lambda: self._ports.portfolio(manifest, research, None)
        )
        if candidate.outcome is not RunOutcome.RUNNING:
            return self._terminal(record, candidate.outcome)
        critique, record = self._step(
            record, Step.CRITIC, lambda: self._ports.critic(manifest, candidate)
        )
        disposition = critique.critic_disposition
        if disposition is CriticDisposition.WAIT:
            return self._terminal(record, RunOutcome.WAIT)
        if disposition is CriticDisposition.NEEDS_REVIEW:
            return self._terminal(record, RunOutcome.NEEDS_REVIEW)
        if disposition is CriticDisposition.REVISE:
            candidate, record = self._step(
                record,
                Step.REVISION,
                lambda: self._ports.portfolio(manifest, research, critique),
                revision=True,
            )
            if candidate.outcome is not RunOutcome.RUNNING:
                return self._terminal(record, candidate.outcome)
        elif disposition is not CriticDisposition.CLEAR:
            return self._terminal(record, RunOutcome.FAILED, "INVALID_CRITIC_DISPOSITION")
        risk, record = self._step(record, Step.RISK, lambda: self._ports.risk(manifest, candidate))
        if risk.risk_approved is not True:
            return self._terminal(record, RunOutcome.REJECTED)
        execution, record = self._step(
            record, Step.EXECUTION, lambda: self._ports.execute(manifest, candidate)
        )
        return self._terminal(
            record,
            RunOutcome.ACCEPTED if execution.outcome is RunOutcome.RUNNING else execution.outcome,
        )

    def _step(
        self,
        record: RunRecord,
        step: Step,
        invoke: Callable[[], StepResult],
        *,
        revision: bool = False,
    ) -> tuple[StepResult, RunRecord]:
        existing = record.result_for(step)
        if existing is not None:
            return existing, record
        if self._now() >= record.manifest.deadline:
            raise RuntimeError("run deadline exceeded")
        result = invoke()
        usage = record.usage.plus(result.usage)
        self._require_budget(record.manifest, usage)
        checkpoint = Checkpoint(
            step=step, result=result, usage_after=usage, completed_at=self._now()
        )
        record = record.model_copy(
            update={
                "checkpoints": (*record.checkpoints, checkpoint),
                "revision_count": record.revision_count + int(revision),
            }
        )
        return result, self._store.save(record)

    @staticmethod
    def _require_budget(manifest: RunManifest, usage: BudgetUsage) -> None:
        if (
            usage.model_calls > manifest.max_model_calls
            or usage.tool_calls > manifest.max_tool_calls
            or usage.tokens > manifest.max_tokens
            or usage.cost > manifest.max_cost
        ):
            raise RuntimeError("shared run budget exceeded")

    def _terminal(
        self, record: RunRecord, outcome: RunOutcome, failure_code: str | None = None
    ) -> RunRecord:
        return self._store.save(
            record.model_copy(update={"outcome": outcome, "failure_code": failure_code})
        )

    @staticmethod
    def _result(record: RunRecord) -> WorkflowResult:
        return WorkflowResult(
            run_id=record.manifest.run_id,
            outcome=record.outcome,
            completed_steps=tuple(item.step for item in record.checkpoints),
            usage=record.usage,
            revision_count=record.revision_count,
            failure_code=record.failure_code,
        )

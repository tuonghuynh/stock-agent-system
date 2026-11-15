from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID, uuid4

import pytest

from stock_agent.coordinator import (
    BudgetUsage,
    Coordinator,
    CriticDisposition,
    InMemoryRunStore,
    RunOutcome,
    Step,
    StepResult,
)
from stock_agent.domain.models import RunManifest, RunStatus

NOW = datetime(2026, 11, 14, 20, tzinfo=UTC)


def manifest(*, run_id: UUID | None = None, objective: str = "Evaluate AAPL") -> RunManifest:
    return RunManifest(
        run_id=run_id or uuid4(),
        trace_id="trace-1",
        objective=objective,
        symbols=("AAPL",),
        horizon="20 trading days",
        as_of=NOW,
        policy_version="1",
        release_version="release-1",
        workflow_version="workflow-1",
        data_snapshot_id=uuid4(),
        model_versions={"research": "fake-1"},
        prompt_versions={"research": "1"},
        tool_versions={"evidence": "1"},
        deadline=NOW + timedelta(minutes=5),
        max_model_calls=4,
        max_tool_calls=4,
        max_tokens=1000,
        max_cost=Decimal("1"),
        allowed_actions=("READ",),
        prohibited_actions=("BROKER", "DELEGATE"),
        status=RunStatus.CREATED,
    )


class FakePorts:
    def __init__(self, disposition: CriticDisposition = CriticDisposition.CLEAR) -> None:
        self.disposition = disposition
        self.calls: list[str] = []
        self.fail_portfolio_once = False
        self.risk_approved = True

    def _result(self, name: str, **updates: object) -> StepResult:
        self.calls.append(name)
        return StepResult(
            reference=f"{name}:1",
            usage=BudgetUsage(
                model_calls=int(name in {"research", "portfolio", "critic", "revision"}), tokens=10
            ),
            **updates,
        )

    def evidence(self, manifest: RunManifest) -> StepResult:
        return self._result("evidence")

    def research(self, manifest: RunManifest, evidence: StepResult) -> StepResult:
        return self._result("research")

    def portfolio(
        self, manifest: RunManifest, research: StepResult, critique: StepResult | None
    ) -> StepResult:
        name = "revision" if critique is not None else "portfolio"
        if self.fail_portfolio_once:
            self.fail_portfolio_once = False
            raise RuntimeError("interrupt")
        return self._result(name)

    def critic(self, manifest: RunManifest, candidate: StepResult) -> StepResult:
        return self._result("critic", critic_disposition=self.disposition)

    def risk(self, manifest: RunManifest, candidate: StepResult) -> StepResult:
        return self._result("risk", risk_approved=self.risk_approved)

    def execute(self, manifest: RunManifest, candidate: StepResult) -> StepResult:
        return self._result("execution", outcome=RunOutcome.ACCEPTED)


def test_at007_fixed_graph_terminates_with_one_bounded_revision() -> None:
    ports = FakePorts(CriticDisposition.REVISE)
    result = Coordinator(InMemoryRunStore(), ports, lambda: NOW).run(manifest())
    assert result.outcome is RunOutcome.ACCEPTED and result.revision_count == 1
    assert result.completed_steps == tuple(Step)
    assert ports.calls == [
        "evidence",
        "research",
        "portfolio",
        "critic",
        "revision",
        "risk",
        "execution",
    ]
    assert result.usage.model_calls == 4


def test_at033_restart_resumes_without_rerunning_checkpointed_steps() -> None:
    store = InMemoryRunStore()
    ports = FakePorts()
    ports.fail_portfolio_once = True
    frozen = manifest()
    first = Coordinator(store, ports, lambda: NOW).run(frozen)
    assert first.outcome is RunOutcome.FAILED and first.completed_steps == (
        Step.EVIDENCE,
        Step.RESEARCH,
    )
    second = Coordinator(store, ports, lambda: NOW).run(frozen)
    assert second.outcome is RunOutcome.ACCEPTED
    assert (
        ports.calls.count("evidence")
        == ports.calls.count("research")
        == ports.calls.count("portfolio")
        == 1
    )


def test_non_retryable_terminal_outcome_cannot_be_reopened() -> None:
    store = InMemoryRunStore()
    ports = FakePorts(CriticDisposition.WAIT)
    frozen = manifest()
    first = Coordinator(store, ports, lambda: NOW).run(frozen)
    assert first.outcome is RunOutcome.WAIT
    assert Coordinator(store, ports, lambda: NOW).run(frozen) == first
    with pytest.raises(ValueError, match="only STEP_FAILURE"):
        store.resume_step_failure(frozen.run_id)
    record = store.get(frozen.run_id)
    assert record is not None
    with pytest.raises(ValueError, match="terminal runs"):
        store.save(record.model_copy(update={"outcome": RunOutcome.RUNNING}))


def test_risk_rejection_never_reaches_execution() -> None:
    ports = FakePorts()
    ports.risk_approved = False
    result = Coordinator(InMemoryRunStore(), ports, lambda: NOW).run(manifest())
    assert (
        result.outcome is RunOutcome.REJECTED
        and "execution" not in ports.calls
        and result.completed_steps[-1] is Step.RISK
    )


@pytest.mark.parametrize(
    ("disposition", "expected"),
    [
        (CriticDisposition.WAIT, RunOutcome.WAIT),
        (CriticDisposition.NEEDS_REVIEW, RunOutcome.NEEDS_REVIEW),
    ],
)
def test_safe_critic_terminal_paths(disposition: CriticDisposition, expected: RunOutcome) -> None:
    ports = FakePorts(disposition)
    result = Coordinator(InMemoryRunStore(), ports, lambda: NOW).run(manifest())
    assert (
        result.outcome is expected and "risk" not in ports.calls and "execution" not in ports.calls
    )


def test_shared_budget_and_deadline_fail_closed() -> None:
    limited = manifest().model_copy(update={"max_tokens": 5})
    result = Coordinator(InMemoryRunStore(), FakePorts(), lambda: NOW).run(limited)
    assert result.outcome is RunOutcome.FAILED and result.completed_steps == ()
    expired = manifest().model_copy(update={"deadline": NOW + timedelta(seconds=1)})
    assert (
        Coordinator(InMemoryRunStore(), FakePorts(), lambda: NOW + timedelta(seconds=1))
        .run(expired)
        .outcome
        is RunOutcome.FAILED
    )


def test_changed_objective_requires_new_run() -> None:
    store = InMemoryRunStore()
    frozen = manifest()
    store.create_or_get(frozen)
    with pytest.raises(ValueError, match="new run"):
        store.create_or_get(frozen.model_copy(update={"objective": "Evaluate TSLA"}))
    assert (
        store.create_or_get(manifest(objective="Evaluate TSLA")).manifest.objective
        == "Evaluate TSLA"
    )

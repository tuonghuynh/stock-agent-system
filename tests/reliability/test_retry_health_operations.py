from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import pytest

from stock_agent.reliability import (
    DependencyState,
    FailureClass,
    OperationalHealth,
    ReconciliationSchedule,
    RecoveryAction,
    RetryPolicy,
    SideEffectGate,
)


def test_rel001_only_transient_failures_retry_with_bounded_exponential_backoff() -> None:
    policy = RetryPolicy(maximum_attempts=4, base_delay_seconds=2, maximum_delay_seconds=5)
    assert [
        policy.decide(FailureClass.TRANSIENT, completed_attempts=value).delay_seconds
        for value in (1, 2, 3)
    ] == [2, 4, 5]
    exhausted = policy.decide(FailureClass.TRANSIENT, completed_attempts=4)
    assert exhausted.action is RecoveryAction.FAIL and exhausted.delay_seconds == 0


@pytest.mark.parametrize(
    ("failure", "action"),
    [
        (FailureClass.ANALYTICAL, RecoveryAction.WAIT),
        (FailureClass.VALIDATION, RecoveryAction.NEEDS_REVIEW),
        (FailureClass.SAFETY, RecoveryAction.REJECT),
        (FailureClass.TERMINAL, RecoveryAction.FAIL),
    ],
)
def test_rel002_rel003_non_transient_failures_never_retry(
    failure: FailureClass, action: RecoveryAction
) -> None:
    decision = RetryPolicy().decide(failure, completed_attempts=1)
    assert decision.action is action and decision.delay_seconds == 0


def test_readiness_fails_for_required_dependency_but_liveness_remains_true() -> None:
    health = OperationalHealth()
    health.record(DependencyState("database", True))
    health.record(DependencyState("migrations", False, detail="pending"))
    health.record(DependencyState("optional-model", False, required=False))
    assert health.live
    assert not health.ready
    assert health.failed_required() == ("migrations",)
    health.record(DependencyState("migrations", True))
    assert health.ready


def test_reconciliation_schedule_restores_cadence_from_persisted_checkpoint() -> None:
    now = datetime(2026, 11, 14, 20, tzinfo=UTC)
    schedule = ReconciliationSchedule(interval=timedelta(seconds=30))
    assert schedule.due(now)
    persisted = schedule.completed(now)
    restored = ReconciliationSchedule(
        interval=persisted.interval,
        last_completed_at=persisted.last_completed_at,
    )
    assert not restored.due(now + timedelta(seconds=29))
    assert restored.due(now + timedelta(seconds=30))


@dataclass
class AuditProbe:
    available: bool = True


def test_at034_audit_failure_blocks_side_effect_and_pause_is_non_destructive() -> None:
    audit = AuditProbe(available=False)
    gate = SideEffectGate(audit)
    with pytest.raises(PermissionError, match="REQUIRED_AUDIT_UNAVAILABLE"):
        gate.require_new_side_effect()
    paused = gate.state()
    assert paused.paused and paused.monitoring_enabled and paused.reconciliation_enabled
    assert not paused.cancel_requested and not paused.liquidation_requested


def test_rel007_cancel_and_liquidation_are_separate_explicit_operations() -> None:
    gate = SideEffectGate(AuditProbe())
    paused = gate.pause("RECONCILIATION_FAILURE")
    assert not paused.cancel_requested and not paused.liquidation_requested
    canceled = gate.request_cancel_open_orders()
    assert canceled.cancel_requested and not canceled.liquidation_requested
    liquidated = gate.request_liquidation()
    assert liquidated.cancel_requested and liquidated.liquidation_requested

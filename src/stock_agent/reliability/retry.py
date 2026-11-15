"""Bounded retry classification and deterministic exponential backoff."""

from dataclasses import dataclass

from stock_agent.reliability.models import (
    FailureClass,
    RecoveryAction,
    RetryDecision,
)


@dataclass(frozen=True, slots=True)
class RetryPolicy:
    maximum_attempts: int = 3
    base_delay_seconds: int = 1
    maximum_delay_seconds: int = 30

    def __post_init__(self) -> None:
        if self.maximum_attempts < 1:
            raise ValueError("maximum_attempts must be positive")
        if self.base_delay_seconds < 1 or self.maximum_delay_seconds < self.base_delay_seconds:
            raise ValueError("backoff bounds are invalid")

    def decide(self, failure: FailureClass, *, completed_attempts: int) -> RetryDecision:
        if completed_attempts < 1:
            raise ValueError("completed_attempts must be positive")
        next_attempt = completed_attempts + 1
        if failure is FailureClass.TRANSIENT and next_attempt <= self.maximum_attempts:
            delay = min(
                self.base_delay_seconds * (2 ** (completed_attempts - 1)),
                self.maximum_delay_seconds,
            )
            return RetryDecision(
                action=RecoveryAction.RETRY,
                delay_seconds=delay,
                next_attempt=next_attempt,
                reason="identified transient failure within retry budget",
            )
        actions = {
            FailureClass.ANALYTICAL: RecoveryAction.WAIT,
            FailureClass.VALIDATION: RecoveryAction.NEEDS_REVIEW,
            FailureClass.SAFETY: RecoveryAction.REJECT,
            FailureClass.TERMINAL: RecoveryAction.FAIL,
            FailureClass.TRANSIENT: RecoveryAction.FAIL,
        }
        return RetryDecision(
            action=actions[failure],
            delay_seconds=0,
            next_attempt=next_attempt,
            reason=(
                "transient retry budget exhausted"
                if failure is FailureClass.TRANSIENT
                else "failure class is not retryable"
            ),
        )

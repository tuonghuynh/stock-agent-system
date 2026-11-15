"""Deterministic reconciliation cadence and restart checkpoint."""

from dataclasses import dataclass, replace
from datetime import datetime, timedelta


@dataclass(frozen=True, slots=True)
class ReconciliationSchedule:
    interval: timedelta
    last_completed_at: datetime | None = None

    def __post_init__(self) -> None:
        if self.interval <= timedelta(0):
            raise ValueError("reconciliation interval must be positive")

    def due(self, now: datetime) -> bool:
        return (
            self.last_completed_at is None
            or now >= self.last_completed_at + self.interval
        )

    def completed(self, at: datetime) -> "ReconciliationSchedule":
        if self.last_completed_at is not None and at < self.last_completed_at:
            raise ValueError("reconciliation checkpoint cannot move backward")
        return replace(self, last_completed_at=at)

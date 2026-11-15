"""Strict reliability boundary models."""

from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ReliabilityModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class WorkStatus(StrEnum):
    PENDING = "PENDING"
    CLAIMED = "CLAIMED"
    COMPLETED = "COMPLETED"
    TERMINAL = "TERMINAL"


class WorkClaim(ReliabilityModel):
    work_id: UUID
    kind: str = Field(min_length=1)
    reference: str = Field(min_length=1)
    status: WorkStatus = WorkStatus.PENDING
    owner: str | None = None
    lease_expires_at: datetime | None = None
    attempts: int = Field(default=0, ge=0)
    completed_at: datetime | None = None
    failure_code: str | None = None

    @model_validator(mode="after")
    def consistent_state(self) -> "WorkClaim":
        if self.status is WorkStatus.CLAIMED:
            if self.owner is None or self.lease_expires_at is None:
                raise ValueError("claimed work requires owner and lease")
        elif self.owner is not None or self.lease_expires_at is not None:
            raise ValueError("only claimed work may carry owner or lease")
        if self.status is WorkStatus.COMPLETED and self.completed_at is None:
            raise ValueError("completed work requires completed_at")
        if self.status is WorkStatus.TERMINAL and not self.failure_code:
            raise ValueError("terminal work requires failure_code")
        return self


class FailureClass(StrEnum):
    TRANSIENT = "TRANSIENT"
    ANALYTICAL = "ANALYTICAL"
    VALIDATION = "VALIDATION"
    SAFETY = "SAFETY"
    TERMINAL = "TERMINAL"


class RecoveryAction(StrEnum):
    RETRY = "RETRY"
    WAIT = "WAIT"
    NEEDS_REVIEW = "NEEDS_REVIEW"
    REJECT = "REJECT"
    FAIL = "FAIL"


class RetryDecision(ReliabilityModel):
    action: RecoveryAction
    delay_seconds: int = Field(ge=0)
    next_attempt: int = Field(ge=1)
    reason: str = Field(min_length=1)

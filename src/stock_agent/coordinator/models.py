from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from stock_agent.domain.models import RunManifest


class CoordinatorModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class Step(StrEnum):
    EVIDENCE = "EVIDENCE"
    RESEARCH = "RESEARCH"
    PORTFOLIO = "PORTFOLIO"
    CRITIC = "CRITIC"
    REVISION = "REVISION"
    RISK = "RISK"
    EXECUTION = "EXECUTION"


class RunOutcome(StrEnum):
    RUNNING = "RUNNING"
    PROPOSED = "PROPOSED"
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"
    WAIT = "WAIT"
    NEEDS_REVIEW = "NEEDS_REVIEW"
    FAILED = "FAILED"


class CriticDisposition(StrEnum):
    CLEAR = "CLEAR"
    REVISE = "REVISE"
    WAIT = "WAIT"
    NEEDS_REVIEW = "NEEDS_REVIEW"


class BudgetUsage(CoordinatorModel):
    model_calls: int = Field(default=0, ge=0)
    tool_calls: int = Field(default=0, ge=0)
    tokens: int = Field(default=0, ge=0)
    cost: Decimal = Field(default=Decimal(0), ge=0)

    def plus(self, other: "BudgetUsage") -> "BudgetUsage":
        return BudgetUsage(
            model_calls=self.model_calls + other.model_calls,
            tool_calls=self.tool_calls + other.tool_calls,
            tokens=self.tokens + other.tokens,
            cost=self.cost + other.cost,
        )


class StepResult(CoordinatorModel):
    reference: str = Field(min_length=1)
    usage: BudgetUsage = BudgetUsage()
    outcome: RunOutcome = RunOutcome.RUNNING
    critic_disposition: CriticDisposition | None = None
    risk_approved: bool | None = None


class Checkpoint(CoordinatorModel):
    step: Step
    result: StepResult
    usage_after: BudgetUsage
    completed_at: datetime


class RunRecord(CoordinatorModel):
    manifest: RunManifest
    checkpoints: tuple[Checkpoint, ...] = ()
    outcome: RunOutcome = RunOutcome.RUNNING
    revision_count: int = Field(default=0, ge=0, le=1)
    failure_code: str | None = None

    @model_validator(mode="after")
    def unique_steps(self) -> "RunRecord":
        steps = [item.step for item in self.checkpoints]
        if len(steps) != len(set(steps)):
            raise ValueError("a workflow step may be checkpointed only once")
        return self

    @property
    def usage(self) -> BudgetUsage:
        return self.checkpoints[-1].usage_after if self.checkpoints else BudgetUsage()

    def result_for(self, step: Step) -> StepResult | None:
        return next((item.result for item in self.checkpoints if item.step is step), None)


class WorkflowResult(CoordinatorModel):
    run_id: UUID
    outcome: RunOutcome
    completed_steps: tuple[Step, ...]
    usage: BudgetUsage
    revision_count: int
    failure_code: str | None = None

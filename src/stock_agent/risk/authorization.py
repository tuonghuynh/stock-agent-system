"""Consistent freshness, deterministic risk and reservation authorization."""

from dataclasses import dataclass

from stock_agent.domain.models import RiskCheck, RiskDecisionValue
from stock_agent.risk.engine import DeterministicRiskEngine
from stock_agent.risk.freshness import RiskDataTimestamps, freshness_checks
from stock_agent.risk.models import RiskContext
from stock_agent.risk.pause import PauseController
from stock_agent.risk.reservations import (
    Reservation,
    ReservationCapacity,
    ReservationRequest,
    ReservationStore,
)


@dataclass(frozen=True, slots=True)
class AuthorizationOutcome:
    approved: bool
    checks: tuple[RiskCheck, ...]
    reservation: Reservation | None = None


class RiskAuthorizationService:
    def __init__(
        self,
        engine: DeterministicRiskEngine,
        reservations: ReservationStore,
        pause: PauseController,
    ) -> None:
        self._engine = engine
        self._reservations = reservations
        self._pause = pause

    def authorize(
        self,
        context: RiskContext,
        *,
        timestamps: RiskDataTimestamps,
        request: ReservationRequest,
        capacity: ReservationCapacity,
    ) -> AuthorizationOutcome:
        self._pause.require_submissions_enabled()
        freshness = freshness_checks(
            timestamps, evaluated_at=context.evaluated_at, policy=context.policy.freshness
        )
        decision = self._engine.evaluate(context)
        checks = (*freshness, *decision.checks)
        if not all(check.passed for check in freshness):
            return AuthorizationOutcome(approved=False, checks=checks)
        if decision.decision is not RiskDecisionValue.APPROVED:
            return AuthorizationOutcome(approved=False, checks=checks)
        reservation = self._reservations.reserve(request, capacity)
        return AuthorizationOutcome(approved=True, checks=checks, reservation=reservation)

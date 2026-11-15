"""Latched operational pause controls without portfolio side effects."""

from dataclasses import dataclass
from decimal import Decimal
from threading import RLock

from stock_agent.policy.models import PausePolicy


@dataclass(frozen=True, slots=True)
class PauseSignals:
    daily_loss_pct: Decimal = Decimal(0)
    weekly_loss_pct: Decimal = Decimal(0)
    drawdown_pct: Decimal = Decimal(0)
    consecutive_system_rejections: int = 0
    reconciliation_failed: bool = False
    required_audit_failed: bool = False


@dataclass(frozen=True, slots=True)
class PauseState:
    paused: bool
    reasons: tuple[str, ...]
    monitoring_enabled: bool = True
    reconciliation_enabled: bool = True
    cancel_orders_requested: bool = False
    liquidation_requested: bool = False


class PauseController:
    """Latches automatic safety pauses until an explicit operator reset."""

    def __init__(self, policy: PausePolicy) -> None:
        self._policy = policy
        self._reasons: tuple[str, ...] = ()
        self._lock = RLock()

    def observe(self, signals: PauseSignals) -> PauseState:
        reasons: list[str] = []
        if signals.daily_loss_pct >= self._policy.daily_loss_pct:
            reasons.append("DAILY_LOSS")
        if signals.weekly_loss_pct >= self._policy.weekly_loss_pct:
            reasons.append("WEEKLY_LOSS")
        if signals.drawdown_pct >= self._policy.peak_to_trough_drawdown_pct:
            reasons.append("DRAWDOWN")
        if signals.consecutive_system_rejections >= self._policy.consecutive_system_rejections:
            reasons.append("SYSTEM_REJECTIONS")
        if signals.reconciliation_failed and self._policy.pause_on_reconciliation_failure:
            reasons.append("RECONCILIATION_FAILURE")
        if signals.required_audit_failed and self._policy.pause_on_required_audit_failure:
            reasons.append("AUDIT_FAILURE")
        with self._lock:
            if reasons:
                self._reasons = tuple(dict.fromkeys((*self._reasons, *reasons)))
            return self.state()

    def require_submissions_enabled(self) -> None:
        with self._lock:
            if self._reasons:
                raise PermissionError("new submissions are paused: " + ", ".join(self._reasons))

    def reset_by_operator(self) -> PauseState:
        with self._lock:
            self._reasons = ()
            return self.state()

    def state(self) -> PauseState:
        with self._lock:
            return PauseState(paused=bool(self._reasons), reasons=self._reasons)

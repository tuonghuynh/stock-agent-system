"""Required-audit side-effect gate and explicit operational actions."""

from dataclasses import dataclass
from threading import RLock
from typing import Protocol


class AuditAvailability(Protocol):
    @property
    def available(self) -> bool: ...


@dataclass(frozen=True, slots=True)
class OperationState:
    paused: bool
    pause_reason: str | None
    monitoring_enabled: bool = True
    reconciliation_enabled: bool = True
    cancel_requested: bool = False
    liquidation_requested: bool = False


class SideEffectGate:
    """Fail closed before side effects while keeping destructive actions explicit."""

    def __init__(self, audit: AuditAvailability) -> None:
        self._audit = audit
        self._pause_reason: str | None = None
        self._cancel_requested = False
        self._liquidation_requested = False
        self._lock = RLock()

    def require_new_side_effect(self) -> None:
        with self._lock:
            if not self._audit.available:
                self._pause_reason = "REQUIRED_AUDIT_UNAVAILABLE"
            if self._pause_reason is not None:
                raise PermissionError(f"new side effects blocked: {self._pause_reason}")

    def pause(self, reason: str) -> OperationState:
        if not reason.strip():
            raise ValueError("pause reason is required")
        with self._lock:
            self._pause_reason = reason
            return self.state()

    def request_cancel_open_orders(self) -> OperationState:
        with self._lock:
            self._cancel_requested = True
            return self.state()

    def request_liquidation(self) -> OperationState:
        with self._lock:
            self._liquidation_requested = True
            return self.state()

    def state(self) -> OperationState:
        with self._lock:
            return OperationState(
                paused=self._pause_reason is not None,
                pause_reason=self._pause_reason,
                cancel_requested=self._cancel_requested,
                liquidation_requested=self._liquidation_requested,
            )

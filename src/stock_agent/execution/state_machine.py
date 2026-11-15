"""Explicit deterministic trade-intent state transitions."""

from stock_agent.domain.models import IntentStatus


class InvalidIntentTransition(ValueError):
    pass


_ALLOWED: dict[IntentStatus, frozenset[IntentStatus]] = {
    IntentStatus.CREATED: frozenset({IntentStatus.RESERVED, IntentStatus.REJECTED}),
    IntentStatus.RESERVED: frozenset(
        {IntentStatus.SUBMITTING, IntentStatus.REJECTED, IntentStatus.EXPIRED}
    ),
    IntentStatus.SUBMITTING: frozenset(
        {
            IntentStatus.SUBMITTED,
            IntentStatus.UNKNOWN,
            IntentStatus.REJECTED,
            IntentStatus.EXPIRED,
        }
    ),
    IntentStatus.UNKNOWN: frozenset({IntentStatus.RECONCILING}),
    IntentStatus.RECONCILING: frozenset(
        {IntentStatus.SUBMITTED, IntentStatus.REJECTED}
    ),
    IntentStatus.SUBMITTED: frozenset(
        {
            IntentStatus.PARTIALLY_FILLED,
            IntentStatus.FILLED,
            IntentStatus.PENDING_CANCEL,
            IntentStatus.REJECTED,
            IntentStatus.EXPIRED,
            IntentStatus.REPLACED,
        }
    ),
    IntentStatus.PARTIALLY_FILLED: frozenset(
        {
            IntentStatus.PARTIALLY_FILLED,
            IntentStatus.FILLED,
            IntentStatus.PENDING_CANCEL,
        }
    ),
    IntentStatus.PENDING_CANCEL: frozenset(
        {IntentStatus.CANCELED, IntentStatus.FILLED, IntentStatus.PARTIALLY_FILLED}
    ),
}


def require_transition(current: IntentStatus, target: IntentStatus) -> None:
    if target not in _ALLOWED.get(current, frozenset()):
        raise InvalidIntentTransition(f"invalid trade-intent transition: {current} -> {target}")

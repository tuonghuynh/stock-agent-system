"""Deterministic recovery, fill accounting and broker reconciliation."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from threading import RLock
from uuid import UUID

from stock_agent.domain.models import IntentStatus, TradeIntent
from stock_agent.execution.broker import BrokerAdapter, BrokerOrder, BrokerOrderStatus
from stock_agent.execution.identity import derive_client_order_id
from stock_agent.execution.state_machine import require_transition
from stock_agent.execution.store import InMemoryExecutionStore, StoredExecution


@dataclass(frozen=True, slots=True)
class Fill:
    broker_fill_id: str
    broker_order_id: str
    quantity: Decimal
    price: Decimal
    executed_at: datetime


@dataclass(frozen=True, slots=True)
class ExecutionBalance:
    position_quantity: Decimal = Decimal(0)
    reserved_quantity: Decimal = Decimal(0)
    filled_quantity: Decimal = Decimal(0)


@dataclass(frozen=True, slots=True)
class ReconciliationSnapshot:
    cash: Decimal
    positions: tuple[tuple[str, Decimal], ...]
    open_client_order_ids: tuple[str, ...]
    pending_reservations: tuple[tuple[str, Decimal], ...]


class FillLedger:
    """Deduplicates fills and releases only the filled portion of a reservation."""

    def __init__(self, reserved_quantity: Decimal) -> None:
        self._balance = ExecutionBalance(reserved_quantity=reserved_quantity)
        self._fill_ids: set[str] = set()
        self._lock = RLock()

    def apply(self, fill: Fill) -> ExecutionBalance:
        if fill.quantity <= 0 or fill.price <= 0:
            raise ValueError("fill quantity and price must be positive")
        with self._lock:
            if fill.broker_fill_id in self._fill_ids:
                return self._balance
            if fill.quantity > self._balance.reserved_quantity:
                raise ValueError("fill exceeds remaining reservation")
            self._fill_ids.add(fill.broker_fill_id)
            self._balance = ExecutionBalance(
                position_quantity=self._balance.position_quantity + fill.quantity,
                reserved_quantity=self._balance.reserved_quantity - fill.quantity,
                filled_quantity=self._balance.filled_quantity + fill.quantity,
            )
            return self._balance


class ExecutionPause:
    def __init__(self) -> None:
        self._reason: str | None = None

    @property
    def paused(self) -> bool:
        return self._reason is not None

    @property
    def reason(self) -> str | None:
        return self._reason

    def pause(self, reason: str) -> None:
        self._reason = reason


_INTENT_BY_BROKER_STATUS: dict[BrokerOrderStatus, IntentStatus] = {
    BrokerOrderStatus.ACCEPTED: IntentStatus.SUBMITTED,
    BrokerOrderStatus.NEW: IntentStatus.SUBMITTED,
    BrokerOrderStatus.PARTIALLY_FILLED: IntentStatus.PARTIALLY_FILLED,
    BrokerOrderStatus.FILLED: IntentStatus.FILLED,
    BrokerOrderStatus.PENDING_CANCEL: IntentStatus.PENDING_CANCEL,
    BrokerOrderStatus.CANCELED: IntentStatus.CANCELED,
    BrokerOrderStatus.REJECTED: IntentStatus.REJECTED,
    BrokerOrderStatus.EXPIRED: IntentStatus.EXPIRED,
    BrokerOrderStatus.REPLACED: IntentStatus.REPLACED,
}


class ExecutionReconciler:
    def __init__(
        self,
        store: InMemoryExecutionStore,
        broker: BrokerAdapter,
        pause: ExecutionPause,
    ) -> None:
        self._store = store
        self._broker = broker
        self._pause = pause

    def recover(self, intent_id: UUID) -> StoredExecution:
        stored = self._required(intent_id)
        if stored.intent.status not in {IntentStatus.UNKNOWN, IntentStatus.SUBMITTING}:
            return stored
        current = stored.intent
        if current.status is IntentStatus.SUBMITTING:
            current = self._move(current, IntentStatus.UNKNOWN).intent
        reconciling = self._move(current, IntentStatus.RECONCILING).intent
        order = self._broker.find_by_client_order_id(derive_client_order_id(intent_id))
        if order is None:
            return self._move(reconciling, IntentStatus.REJECTED)
        self._move(reconciling, IntentStatus.SUBMITTED)
        attached = self._store.attach_order(intent_id, order)
        return self.apply_order(attached, order)

    def reconcile_open_orders(self) -> tuple[StoredExecution, ...]:
        broker_orders = {order.client_order_id: order for order in self._broker.list_open_orders()}
        local_open = tuple(
            item
            for item in self._store.all_executions()
            if item.intent.status
            in {IntentStatus.SUBMITTED, IntentStatus.PARTIALLY_FILLED, IntentStatus.PENDING_CANCEL}
        )
        local_ids = {
            derive_client_order_id(item.intent.intent_id): item for item in local_open
        }
        if set(broker_orders) != set(local_ids):
            self._pause.pause("material local/broker open-order mismatch")
            return local_open
        return tuple(
            self.apply_order(item, broker_orders[client_id])
            for client_id, item in local_ids.items()
        )

    def reconcile_snapshot(
        self,
        *,
        local: ReconciliationSnapshot,
        broker: ReconciliationSnapshot,
    ) -> bool:
        """Compare all material execution state and pause on any mismatch."""
        if local != broker:
            self._pause.pause("material local/broker state mismatch")
            return False
        return True

    def apply_order(self, stored: StoredExecution, order: BrokerOrder) -> StoredExecution:
        target = _INTENT_BY_BROKER_STATUS[BrokerOrderStatus(order.status)]
        current = stored.intent.status
        if target == current:
            return self._store.attach_order(stored.intent.intent_id, order)
        require_transition(current, target)
        updated = stored.intent.model_copy(update={"status": target})
        self._store.update_intent(updated)
        return self._store.attach_order(updated.intent_id, order)

    def _required(self, intent_id: UUID) -> StoredExecution:
        stored = self._store.find_by_intent_id(intent_id)
        if stored is None:
            raise KeyError(intent_id)
        return stored

    def _move(self, intent: TradeIntent, target: IntentStatus) -> StoredExecution:
        typed = self._required(intent.intent_id).intent
        require_transition(typed.status, target)
        return self._store.update_intent(typed.model_copy(update={"status": target}))

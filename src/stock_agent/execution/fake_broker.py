"""Deterministic paper-only broker used by tests and development."""

from collections.abc import Callable
from datetime import datetime
from decimal import Decimal
from threading import RLock

from stock_agent.domain.models import TradeEnvironment, TradeIntent
from stock_agent.execution.broker import BrokerOrder


class FakeBroker:
    def __init__(self, now: Callable[[], datetime]) -> None:
        self._now = now
        self._lock = RLock()
        self._orders: dict[str, BrokerOrder] = {}
        self._submission_count = 0

    def submit(self, intent: TradeIntent, client_order_id: str) -> BrokerOrder:
        if intent.environment is not TradeEnvironment.PAPER:
            raise ValueError("fake broker accepts paper intents only")
        with self._lock:
            self._submission_count += 1
            existing = self._orders.get(client_order_id)
            if existing is not None:
                return existing
            timestamp = self._now()
            order = BrokerOrder(
                broker_order_id=f"fake-{intent.intent_id.hex}",
                client_order_id=client_order_id,
                status="ACCEPTED",
                requested_quantity=intent.quantity,
                filled_quantity=Decimal(0),
                average_fill_price=None,
                submitted_at=timestamp,
                updated_at=timestamp,
            )
            self._orders[client_order_id] = order
            return order

    def find_by_client_order_id(self, client_order_id: str) -> BrokerOrder | None:
        with self._lock:
            return self._orders.get(client_order_id)

    @property
    def submission_count(self) -> int:
        with self._lock:
            return self._submission_count

    @property
    def order_count(self) -> int:
        with self._lock:
            return len(self._orders)

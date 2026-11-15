"""Strict paper-broker boundary that is never exposed to model agents."""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Protocol

from stock_agent.domain.models import TradeIntent


class BrokerOrderStatus(StrEnum):
    ACCEPTED = "ACCEPTED"
    NEW = "NEW"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    FILLED = "FILLED"
    PENDING_CANCEL = "PENDING_CANCEL"
    CANCELED = "CANCELED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"
    REPLACED = "REPLACED"


class SubmissionTimeout(TimeoutError):
    """The broker may have accepted an order, but its response was lost."""


@dataclass(frozen=True, slots=True)
class BrokerOrder:
    broker_order_id: str
    client_order_id: str
    status: str
    requested_quantity: Decimal
    filled_quantity: Decimal
    average_fill_price: Decimal | None
    submitted_at: datetime
    updated_at: datetime
    raw_response_hash: str = "0" * 64


class BrokerAdapter(Protocol):
    """Credentialed execution interface; implementations must remain paper-only."""

    def submit(self, intent: TradeIntent, client_order_id: str) -> BrokerOrder: ...

    def find_by_client_order_id(self, client_order_id: str) -> BrokerOrder | None: ...

    def cancel(self, broker_order_id: str) -> BrokerOrder: ...

    def list_open_orders(self) -> tuple[BrokerOrder, ...]: ...

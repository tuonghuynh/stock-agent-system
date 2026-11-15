"""Strict paper-broker boundary that is never exposed to model agents."""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Protocol

from stock_agent.domain.models import TradeIntent


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


class BrokerAdapter(Protocol):
    """Credentialed execution interface; implementations must remain paper-only."""

    def submit(self, intent: TradeIntent, client_order_id: str) -> BrokerOrder: ...

    def find_by_client_order_id(self, client_order_id: str) -> BrokerOrder | None: ...

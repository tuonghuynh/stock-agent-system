"""Strict Alpaca paper adapter with an injectable HTTP transport."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from datetime import datetime
from decimal import Decimal
from typing import Protocol

from stock_agent.domain.models import TradeIntent
from stock_agent.execution.broker import BrokerOrder, BrokerOrderStatus

PAPER_BASE_URL = "https://paper-api.alpaca.markets"


class PaperTransport(Protocol):
    def post(self, path: str, payload: Mapping[str, str]) -> Mapping[str, object]: ...

    def get(self, path: str) -> Mapping[str, object] | None: ...

    def delete(self, path: str) -> Mapping[str, object]: ...


_STATUS_MAP: dict[str, BrokerOrderStatus] = {
    "accepted": BrokerOrderStatus.ACCEPTED,
    "new": BrokerOrderStatus.NEW,
    "partially_filled": BrokerOrderStatus.PARTIALLY_FILLED,
    "filled": BrokerOrderStatus.FILLED,
    "pending_cancel": BrokerOrderStatus.PENDING_CANCEL,
    "canceled": BrokerOrderStatus.CANCELED,
    "cancelled": BrokerOrderStatus.CANCELED,
    "rejected": BrokerOrderStatus.REJECTED,
    "expired": BrokerOrderStatus.EXPIRED,
    "replaced": BrokerOrderStatus.REPLACED,
}


class AlpacaPaperAdapter:
    """Paper-only adapter; construction rejects every non-paper endpoint."""

    def __init__(self, transport: PaperTransport, *, base_url: str = PAPER_BASE_URL) -> None:
        if base_url.rstrip("/") != PAPER_BASE_URL:
            raise ValueError("Alpaca adapter requires the canonical paper endpoint")
        self._transport = transport

    def submit(self, intent: TradeIntent, client_order_id: str) -> BrokerOrder:
        raw = self._transport.post(
            "/v2/orders",
            {
                "symbol": intent.symbol,
                "qty": _decimal(intent.quantity),
                "side": intent.side.value.lower(),
                "type": "limit",
                "time_in_force": "day",
                "limit_price": _decimal(intent.limit_price),
                "client_order_id": client_order_id,
                "extended_hours": "false",
            },
        )
        return _parse_order(raw)

    def find_by_client_order_id(self, client_order_id: str) -> BrokerOrder | None:
        path = f"/v2/orders:by_client_order_id?client_order_id={client_order_id}"
        raw = self._transport.get(path)
        return None if raw is None else _parse_order(raw)

    def cancel(self, broker_order_id: str) -> BrokerOrder:
        return _parse_order(self._transport.delete(f"/v2/orders/{broker_order_id}"))

    def list_open_orders(self) -> tuple[BrokerOrder, ...]:
        raw = self._transport.get("/v2/orders?status=open")
        if raw is None:
            return ()
        items = raw.get("orders")
        if not isinstance(items, list):
            raise ValueError("paper order list response must contain orders")
        return tuple(_parse_order(item) for item in items if isinstance(item, Mapping))


def _parse_order(raw: Mapping[str, object]) -> BrokerOrder:
    status_value = str(raw.get("status", "")).lower()
    try:
        status = _STATUS_MAP[status_value]
    except KeyError as error:
        raise ValueError(f"unsupported Alpaca paper order status: {status_value}") from error
    canonical = json.dumps(dict(raw), sort_keys=True, separators=(",", ":"), default=str)
    return BrokerOrder(
        broker_order_id=str(raw["id"]),
        client_order_id=str(raw["client_order_id"]),
        status=status,
        requested_quantity=Decimal(str(raw["qty"])),
        filled_quantity=Decimal(str(raw.get("filled_qty", "0"))),
        average_fill_price=(
            None
            if raw.get("filled_avg_price") in (None, "")
            else Decimal(str(raw["filled_avg_price"]))
        ),
        submitted_at=datetime.fromisoformat(str(raw["submitted_at"]).replace("Z", "+00:00")),
        updated_at=datetime.fromisoformat(str(raw["updated_at"]).replace("Z", "+00:00")),
        raw_response_hash=hashlib.sha256(canonical.encode()).hexdigest(),
    )


def _decimal(value: Decimal) -> str:
    return format(value.normalize(), "f")

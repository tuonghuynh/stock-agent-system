from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

import pytest

from stock_agent.risk import (
    InMemoryReservationStore,
    OrderSide,
    ReservationCapacity,
    ReservationRejected,
    ReservationRequest,
    ReservationStatus,
)

NOW = datetime(2026, 11, 14, 20, tzinfo=UTC)


def request(side: OrderSide, *, cash: str = "0", quantity: str = "1") -> ReservationRequest:
    return ReservationRequest(
        reservation_id=uuid4(),
        intent_id=uuid4(),
        symbol="AAPL",
        side=side,
        quantity=Decimal(quantity),
        cash_required=Decimal(cash),
        created_at=NOW,
    )


def test_at013_pending_orders_and_local_reservations_reduce_exposure_capacity() -> None:
    store = InMemoryReservationStore()
    capacity = ReservationCapacity(settled_cash=Decimal(100), positions={"AAPL": Decimal(10)},
                                   pending_buy_cash=Decimal(20),
                                   pending_sell_shares={"AAPL": Decimal(3)})
    store.reserve(request(OrderSide.BUY, cash="50"), capacity)
    assert store.active_cash() == Decimal(50)
    with pytest.raises(ReservationRejected, match="pending and local"):
        store.reserve(request(OrderSide.BUY, cash="31"), capacity)

    store.reserve(request(OrderSide.SELL, quantity="4"), capacity)
    assert store.active_shares("AAPL") == Decimal(4)
    with pytest.raises(ReservationRejected, match="pending and local"):
        store.reserve(request(OrderSide.SELL, quantity="4"), capacity)


def test_at014_concurrent_buys_cannot_overspend_cash() -> None:
    store = InMemoryReservationStore()
    capacity = ReservationCapacity(settled_cash=Decimal(100), positions={})
    requests = [request(OrderSide.BUY, cash="60") for _ in range(24)]

    def try_reserve(item: ReservationRequest) -> bool:
        try:
            store.reserve(item, capacity)
        except ReservationRejected:
            return False
        return True

    with ThreadPoolExecutor(max_workers=8) as executor:
        outcomes = list(executor.map(try_reserve, requests))

    assert outcomes.count(True) == 1
    assert store.active_cash() == Decimal(60)


def test_concurrent_sells_cannot_oversell_shares() -> None:
    store = InMemoryReservationStore()
    capacity = ReservationCapacity(settled_cash=Decimal(0), positions={"AAPL": Decimal(10)})
    requests = [request(OrderSide.SELL, quantity="6") for _ in range(24)]

    def try_reserve(item: ReservationRequest) -> bool:
        try:
            store.reserve(item, capacity)
        except ReservationRejected:
            return False
        return True

    with ThreadPoolExecutor(max_workers=8) as executor:
        outcomes = list(executor.map(try_reserve, requests))
    assert outcomes.count(True) == 1
    assert store.active_shares("AAPL") == Decimal(6)


def test_partial_fill_preserves_remainder_until_verified_terminal_state() -> None:
    store = InMemoryReservationStore()
    item = request(OrderSide.BUY, cash="100", quantity="10")
    reserved = store.reserve(
        item, ReservationCapacity(settled_cash=Decimal(100), positions={})
    )
    partial = store.apply_fill(reserved.request.reservation_id, Decimal(4))
    assert partial.remaining_quantity == Decimal(6)
    assert partial.remaining_cash == Decimal(60)
    assert partial.status is ReservationStatus.ACTIVE
    released = store.release_terminal(item.reservation_id)
    assert released.status is ReservationStatus.RELEASED
    assert store.active_cash() == 0


def test_duplicate_intent_returns_same_reservation_idempotently() -> None:
    store = InMemoryReservationStore()
    item = request(OrderSide.BUY, cash="20")
    capacity = ReservationCapacity(settled_cash=Decimal(100), positions={})
    assert store.reserve(item, capacity) == store.reserve(item, capacity)
    assert store.active_cash() == Decimal(20)

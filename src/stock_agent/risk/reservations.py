"""Atomic cash/share reservations used by deterministic authorization."""

from dataclasses import dataclass, replace
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from threading import RLock
from typing import Protocol
from uuid import UUID

from stock_agent.risk.models import OrderSide


class ReservationStatus(StrEnum):
    ACTIVE = "ACTIVE"
    RELEASED = "RELEASED"


@dataclass(frozen=True, slots=True)
class ReservationRequest:
    reservation_id: UUID
    intent_id: UUID
    symbol: str
    side: OrderSide
    quantity: Decimal
    cash_required: Decimal
    created_at: datetime

    def __post_init__(self) -> None:
        if self.quantity <= 0:
            raise ValueError("reservation quantity must be positive")
        if self.cash_required < 0:
            raise ValueError("cash_required must not be negative")
        if self.side is OrderSide.BUY and self.cash_required <= 0:
            raise ValueError("buy reservation requires positive cash")
        if self.side is OrderSide.SELL and self.cash_required != 0:
            raise ValueError("sell reservation cannot reserve cash")


@dataclass(frozen=True, slots=True)
class Reservation:
    request: ReservationRequest
    remaining_quantity: Decimal
    remaining_cash: Decimal
    status: ReservationStatus = ReservationStatus.ACTIVE


@dataclass(frozen=True, slots=True)
class ReservationCapacity:
    settled_cash: Decimal
    positions: dict[str, Decimal]
    pending_buy_cash: Decimal = Decimal(0)
    pending_sell_shares: dict[str, Decimal] | None = None


class ReservationRejected(ValueError):
    """Raised when an atomic reservation would overspend or oversell."""


class ReservationStore(Protocol):
    def reserve(
        self, request: ReservationRequest, capacity: ReservationCapacity
    ) -> Reservation: ...

    def apply_fill(self, reservation_id: UUID, filled_quantity: Decimal) -> Reservation: ...

    def release_terminal(self, reservation_id: UUID) -> Reservation: ...


class InMemoryReservationStore:
    """Thread-safe adapter mirroring a serializable database transaction."""

    def __init__(self) -> None:
        self._reservations: dict[UUID, Reservation] = {}
        self._intent_ids: dict[UUID, UUID] = {}
        self._lock = RLock()

    def reserve(self, request: ReservationRequest, capacity: ReservationCapacity) -> Reservation:
        with self._lock:
            existing_id = self._intent_ids.get(request.intent_id)
            if existing_id is not None:
                return self._reservations[existing_id]
            if request.reservation_id in self._reservations:
                raise ReservationRejected("reservation ID already exists")
            if request.side is OrderSide.BUY:
                available = capacity.settled_cash - capacity.pending_buy_cash - self.active_cash()
                if request.cash_required > available:
                    raise ReservationRejected(
                        "insufficient cash after pending and local reservations"
                    )
            else:
                pending = (capacity.pending_sell_shares or {}).get(request.symbol, Decimal(0))
                available = (
                    capacity.positions.get(request.symbol, Decimal(0))
                    - pending
                    - self.active_shares(request.symbol)
                )
                if request.quantity > available:
                    raise ReservationRejected(
                        "insufficient shares after pending and local reservations"
                    )
            reservation = Reservation(
                request=request,
                remaining_quantity=request.quantity,
                remaining_cash=request.cash_required,
            )
            self._reservations[request.reservation_id] = reservation
            self._intent_ids[request.intent_id] = request.reservation_id
            return reservation

    def apply_fill(self, reservation_id: UUID, filled_quantity: Decimal) -> Reservation:
        if filled_quantity <= 0:
            raise ValueError("filled_quantity must be positive")
        with self._lock:
            current = self._active(reservation_id)
            if filled_quantity > current.remaining_quantity:
                raise ValueError("fill exceeds remaining reservation")
            remaining_quantity = current.remaining_quantity - filled_quantity
            ratio = remaining_quantity / current.request.quantity
            remaining_cash = current.request.cash_required * ratio
            updated = replace(
                current,
                remaining_quantity=remaining_quantity,
                remaining_cash=remaining_cash,
            )
            self._reservations[reservation_id] = updated
            return updated

    def release_terminal(self, reservation_id: UUID) -> Reservation:
        with self._lock:
            current = self._active(reservation_id)
            released = replace(
                current,
                remaining_quantity=Decimal(0),
                remaining_cash=Decimal(0),
                status=ReservationStatus.RELEASED,
            )
            self._reservations[reservation_id] = released
            return released

    def active_cash(self) -> Decimal:
        return sum(
            (item.remaining_cash for item in self._reservations.values()
             if item.status is ReservationStatus.ACTIVE),
            start=Decimal(0),
        )

    def active_shares(self, symbol: str) -> Decimal:
        return sum(
            (item.remaining_quantity for item in self._reservations.values()
             if item.status is ReservationStatus.ACTIVE
             and item.request.side is OrderSide.SELL
             and item.request.symbol == symbol),
            start=Decimal(0),
        )

    def get(self, reservation_id: UUID) -> Reservation | None:
        with self._lock:
            return self._reservations.get(reservation_id)

    def _active(self, reservation_id: UUID) -> Reservation:
        current = self._reservations.get(reservation_id)
        if current is None:
            raise KeyError(reservation_id)
        if current.status is not ReservationStatus.ACTIVE:
            raise ValueError("reservation is already released")
        return current

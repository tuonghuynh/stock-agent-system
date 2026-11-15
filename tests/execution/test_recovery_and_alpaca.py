from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

import pytest

from stock_agent.domain.models import (
    IntentStatus,
    OrderType,
    TimeInForce,
    TradeEnvironment,
    TradeIntent,
    TradeSide,
)
from stock_agent.execution.alpaca import AlpacaPaperAdapter
from stock_agent.execution.broker import BrokerOrder, BrokerOrderStatus, SubmissionTimeout
from stock_agent.execution.fake_broker import FakeBroker
from stock_agent.execution.identity import derive_client_order_id, derive_idempotency_key
from stock_agent.execution.pricing import construct_limit_price
from stock_agent.execution.reconciliation import (
    ExecutionPause,
    ExecutionReconciler,
    Fill,
    FillLedger,
    ReconciliationSnapshot,
)
from stock_agent.execution.service import ExecutionService
from stock_agent.execution.store import InMemoryExecutionStore

NOW = datetime(2026, 11, 14, 18, tzinfo=UTC)


def intent() -> TradeIntent:
    recommendation_id = UUID("11111111-1111-1111-1111-111111111111")
    intent_id = uuid4()
    expires_at = NOW + timedelta(hours=1)
    return TradeIntent(
        intent_id=intent_id,
        idempotency_key=derive_idempotency_key(
            recommendation_id=recommendation_id,
            policy_version="1",
            account_id_hash="account-hash",
            symbol="AAPL",
            side=TradeSide.BUY,
            target_delta=Decimal("10"),
            order_type=OrderType.LIMIT,
            limit_price=Decimal("150"),
            time_in_force=TimeInForce.DAY,
            expires_at=expires_at,
        ),
        recommendation_id=recommendation_id,
        risk_decision_id=uuid4(),
        environment=TradeEnvironment.PAPER,
        symbol="AAPL",
        side=TradeSide.BUY,
        quantity=Decimal("10"),
        order_type=OrderType.LIMIT,
        limit_price=Decimal("150"),
        time_in_force=TimeInForce.DAY,
        expires_at=expires_at,
        policy_version="1",
        created_at=NOW,
        status=IntentStatus.RESERVED,
    )


class AmbiguousBroker:
    def __init__(self) -> None:
        self.fake = FakeBroker(lambda: NOW)

    def submit(self, requested: TradeIntent, client_order_id: str) -> BrokerOrder:
        self.fake.submit(requested, client_order_id)
        raise SubmissionTimeout("response lost after broker acceptance")

    def find_by_client_order_id(self, client_order_id: str) -> BrokerOrder | None:
        return self.fake.find_by_client_order_id(client_order_id)

    def cancel(self, broker_order_id: str) -> BrokerOrder:
        return self.fake.cancel(broker_order_id)

    def list_open_orders(self) -> tuple[BrokerOrder, ...]:
        return self.fake.list_open_orders()


def test_at017_lost_submission_is_reconciled_before_any_retry() -> None:
    store = InMemoryExecutionStore()
    broker = AmbiguousBroker()
    requested = intent()
    unknown = ExecutionService(store, broker, lambda: NOW).submit(requested)

    assert unknown.intent.status is IntentStatus.UNKNOWN
    assert broker.fake.submission_count == 1
    recovered = ExecutionReconciler(store, broker, ExecutionPause()).recover(requested.intent_id)
    assert recovered.intent.status is IntentStatus.SUBMITTED
    assert recovered.order is not None
    assert broker.fake.submission_count == 1


def test_at018_restart_during_submitting_recovers_without_duplicate() -> None:
    store = InMemoryExecutionStore()
    broker = FakeBroker(lambda: NOW)
    requested = intent()
    store.create_if_absent(requested)
    store.update_intent(requested.model_copy(update={"status": IntentStatus.SUBMITTING}))
    broker.submit(requested, derive_client_order_id(requested.intent_id))

    restarted = ExecutionReconciler(store, broker, ExecutionPause())
    result = restarted.recover(requested.intent_id)
    assert result.intent.status is IntentStatus.SUBMITTED
    assert broker.submission_count == 1


def test_at019_partial_fill_updates_position_and_preserves_reservation() -> None:
    ledger = FillLedger(Decimal("10"))
    balance = ledger.apply(
        Fill("fill-1", "order-1", Decimal("4"), Decimal("150"), NOW)
    )
    assert balance.position_quantity == Decimal("4")
    assert balance.filled_quantity == Decimal("4")
    assert balance.reserved_quantity == Decimal("6")
    assert ledger.apply(Fill("fill-1", "order-1", Decimal("4"), Decimal("150"), NOW)) == balance


def test_at020_fill_during_cancellation_wins_terminal_race() -> None:
    store = InMemoryExecutionStore()
    requested = intent()
    store.create_if_absent(requested)
    submitted = requested.model_copy(update={"status": IntentStatus.SUBMITTED})
    store.update_intent(submitted)
    pending = submitted.model_copy(update={"status": IntentStatus.PENDING_CANCEL})
    store.update_intent(pending)
    order = broker_order(requested, BrokerOrderStatus.FILLED, Decimal("10"))

    result = ExecutionReconciler(store, FakeBroker(lambda: NOW), ExecutionPause()).apply_order(
        store.find_by_intent_id(requested.intent_id), order  # type: ignore[arg-type]
    )
    assert result.intent.status is IntentStatus.FILLED
    assert result.order is not None and result.order.filled_quantity == Decimal("10")


def test_at021_stream_loss_uses_rest_open_order_reconciliation() -> None:
    store = InMemoryExecutionStore()
    broker = FakeBroker(lambda: NOW)
    requested = intent()
    stored = ExecutionService(store, broker, lambda: NOW).submit(requested)
    results = ExecutionReconciler(store, broker, ExecutionPause()).reconcile_open_orders()
    assert results == (stored,)


def test_at022_material_mismatch_pauses_new_submission_authority() -> None:
    store = InMemoryExecutionStore()
    requested = intent()
    store.create_if_absent(requested)
    store.update_intent(requested.model_copy(update={"status": IntentStatus.SUBMITTED}))
    pause = ExecutionPause()
    ExecutionReconciler(store, FakeBroker(lambda: NOW), pause).reconcile_open_orders()
    assert pause.paused
    assert pause.reason == "material local/broker open-order mismatch"
    with pytest.raises(RuntimeError, match="paused"):
        ExecutionService(store, FakeBroker(lambda: NOW), lambda: NOW, pause).submit(intent())


def test_exe008_cash_position_order_and_reservation_snapshot_must_reconcile() -> None:
    pause = ExecutionPause()
    reconciler = ExecutionReconciler(InMemoryExecutionStore(), FakeBroker(lambda: NOW), pause)
    local = ReconciliationSnapshot(
        cash=Decimal("1000"),
        positions=(("AAPL", Decimal("4")),),
        open_client_order_ids=("paper-1",),
        pending_reservations=(("paper-1", Decimal("6")),),
    )
    broker = ReconciliationSnapshot(
        cash=Decimal("999"),
        positions=local.positions,
        open_client_order_ids=local.open_client_order_ids,
        pending_reservations=local.pending_reservations,
    )
    assert not reconciler.reconcile_snapshot(local=local, broker=broker)
    assert pause.paused


@pytest.mark.parametrize(
    ("alpaca_status", "expected"),
    [
        ("accepted", BrokerOrderStatus.ACCEPTED),
        ("new", BrokerOrderStatus.NEW),
        ("partially_filled", BrokerOrderStatus.PARTIALLY_FILLED),
        ("filled", BrokerOrderStatus.FILLED),
        ("pending_cancel", BrokerOrderStatus.PENDING_CANCEL),
        ("canceled", BrokerOrderStatus.CANCELED),
        ("rejected", BrokerOrderStatus.REJECTED),
        ("expired", BrokerOrderStatus.EXPIRED),
        ("replaced", BrokerOrderStatus.REPLACED),
    ],
)
def test_at036_alpaca_paper_contract_maps_documented_states(
    alpaca_status: str, expected: BrokerOrderStatus
) -> None:
    transport = StubTransport(alpaca_status)
    requested = intent()
    order = AlpacaPaperAdapter(transport).submit(requested, "paper-id")
    assert order.status is expected
    assert transport.payload == {
        "symbol": "AAPL",
        "qty": "10",
        "side": "buy",
        "type": "limit",
        "time_in_force": "day",
        "limit_price": "150",
        "client_order_id": "paper-id",
        "extended_hours": "false",
    }
    assert len(order.raw_response_hash) == 64


def test_alpaca_adapter_rejects_live_endpoint_and_limit_prices_are_side_safe() -> None:
    with pytest.raises(ValueError, match="paper endpoint"):
        AlpacaPaperAdapter(StubTransport("new"), base_url="https://api.alpaca.markets")
    assert construct_limit_price(
        side=TradeSide.BUY,
        reference_price=Decimal("10.003"),
        offset_bps=10,
        tick_size=Decimal("0.01"),
    ) == Decimal("10.01")
    assert construct_limit_price(
        side=TradeSide.SELL,
        reference_price=Decimal("10.003"),
        offset_bps=10,
        tick_size=Decimal("0.01"),
    ) == Decimal("10.00")


def broker_order(
    requested: TradeIntent, status: BrokerOrderStatus, filled: Decimal
) -> BrokerOrder:
    return BrokerOrder(
        broker_order_id="order-1",
        client_order_id=derive_client_order_id(requested.intent_id),
        status=status,
        requested_quantity=requested.quantity,
        filled_quantity=filled,
        average_fill_price=Decimal("150") if filled else None,
        submitted_at=NOW,
        updated_at=NOW,
    )


class StubTransport:
    def __init__(self, status: str) -> None:
        self.status = status
        self.payload: dict[str, str] | None = None

    def post(self, path: str, payload: Any) -> dict[str, object]:
        assert path == "/v2/orders"
        self.payload = dict(payload)
        return self._order()

    def get(self, path: str) -> dict[str, object] | None:
        return self._order()

    def delete(self, path: str) -> dict[str, object]:
        return self._order()

    def _order(self) -> dict[str, object]:
        return {
            "id": "broker-1",
            "client_order_id": "paper-id",
            "status": self.status,
            "qty": "10",
            "filled_qty": "4" if self.status == "partially_filled" else "0",
            "filled_avg_price": "150" if self.status == "partially_filled" else None,
            "submitted_at": "2026-11-14T18:00:00Z",
            "updated_at": "2026-11-14T18:00:01Z",
        }

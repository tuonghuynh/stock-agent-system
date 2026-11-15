from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from decimal import Decimal
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
from stock_agent.execution.broker import BrokerOrder
from stock_agent.execution.fake_broker import FakeBroker
from stock_agent.execution.identity import derive_client_order_id, derive_idempotency_key
from stock_agent.execution.service import ExecutionService
from stock_agent.execution.state_machine import InvalidIntentTransition, require_transition
from stock_agent.execution.store import InMemoryExecutionStore

NOW = datetime(2026, 11, 14, 18, tzinfo=UTC)
RECOMMENDATION_ID = UUID("11111111-1111-1111-1111-111111111111")
RISK_DECISION_ID = UUID("22222222-2222-2222-2222-222222222222")


def make_intent(*, intent_id: UUID | None = None, key: str | None = None) -> TradeIntent:
    resolved_id = intent_id or uuid4()
    resolved_key = key or derive_idempotency_key(
        recommendation_id=RECOMMENDATION_ID,
        policy_version="1",
        account_id_hash="account-hash",
        symbol="AAPL",
        side=TradeSide.BUY,
        target_delta=Decimal("2.0"),
        order_type=OrderType.LIMIT,
        limit_price=Decimal("150.00"),
        time_in_force=TimeInForce.DAY,
        expires_at=NOW + timedelta(hours=1),
    )
    return TradeIntent(
        intent_id=resolved_id,
        idempotency_key=resolved_key,
        recommendation_id=RECOMMENDATION_ID,
        risk_decision_id=RISK_DECISION_ID,
        environment=TradeEnvironment.PAPER,
        symbol="AAPL",
        side=TradeSide.BUY,
        quantity=Decimal("2"),
        order_type=OrderType.LIMIT,
        limit_price=Decimal("150"),
        time_in_force=TimeInForce.DAY,
        expires_at=NOW + timedelta(hours=1),
        policy_version="1",
        created_at=NOW,
        status=IntentStatus.RESERVED,
    )


def test_at016_duplicate_intent_creates_one_broker_order() -> None:
    store = InMemoryExecutionStore()
    broker = FakeBroker(lambda: NOW)
    service = ExecutionService(store, broker, lambda: NOW)
    intent = make_intent()

    first = service.submit(intent)
    duplicate = service.submit(intent)

    assert duplicate == first
    assert first.intent.status is IntentStatus.SUBMITTED
    assert first.order is not None
    assert first.order.client_order_id == derive_client_order_id(intent.intent_id)
    assert broker.submission_count == 1
    assert broker.order_count == 1


def test_at016_concurrent_duplicate_intents_create_one_broker_order() -> None:
    store = InMemoryExecutionStore()
    broker = FakeBroker(lambda: NOW)
    service = ExecutionService(store, broker, lambda: NOW)
    intent = make_intent()

    with ThreadPoolExecutor(max_workers=8) as executor:
        results = list(executor.map(service.submit, [intent] * 32))

    assert all(result == results[0] for result in results)
    assert broker.submission_count == 1
    assert broker.order_count == 1


def test_intent_is_persisted_before_broker_side_effect() -> None:
    store = InMemoryExecutionStore()
    intent = make_intent()

    class InspectingBroker:
        def submit(self, submitted: TradeIntent, client_order_id: str) -> BrokerOrder:
            persisted = store.find_by_idempotency_key(submitted.idempotency_key)
            assert persisted is not None
            assert persisted.intent.status is IntentStatus.SUBMITTING
            timestamp = NOW
            return BrokerOrder(
                broker_order_id="fake-1",
                client_order_id=client_order_id,
                status="ACCEPTED",
                requested_quantity=submitted.quantity,
                filled_quantity=Decimal(0),
                average_fill_price=None,
                submitted_at=timestamp,
                updated_at=timestamp,
            )

        def find_by_client_order_id(self, client_order_id: str) -> BrokerOrder | None:
            return None

    result = ExecutionService(store, InspectingBroker(), lambda: NOW).submit(intent)
    assert result.intent.status is IntentStatus.SUBMITTED


def test_idempotency_identity_is_canonical_and_parameter_sensitive() -> None:
    base = {
        "recommendation_id": RECOMMENDATION_ID,
        "policy_version": "1",
        "account_id_hash": "account-hash",
        "symbol": "AAPL",
        "side": TradeSide.BUY,
        "target_delta": Decimal("2.0"),
        "order_type": OrderType.LIMIT,
        "limit_price": Decimal("150.00"),
        "time_in_force": TimeInForce.DAY,
        "expires_at": NOW + timedelta(hours=1),
    }
    same = {**base, "target_delta": Decimal("2.000"), "limit_price": Decimal("150")}
    changed = {**base, "limit_price": Decimal("151")}

    assert derive_idempotency_key(**base) == derive_idempotency_key(**same)
    assert derive_idempotency_key(**base) != derive_idempotency_key(**changed)


def test_unknown_cannot_blindly_retry_submission() -> None:
    with pytest.raises(InvalidIntentTransition):
        require_transition(IntentStatus.UNKNOWN, IntentStatus.SUBMITTING)


def test_unreserved_intent_is_rejected_without_broker_side_effect() -> None:
    store = InMemoryExecutionStore()
    broker = FakeBroker(lambda: NOW)
    service = ExecutionService(store, broker, lambda: NOW)
    intent = make_intent().model_copy(update={"status": IntentStatus.CREATED})

    with pytest.raises(ValueError, match="reserved"):
        service.submit(intent)
    assert broker.submission_count == 0
    assert store.find_by_idempotency_key(intent.idempotency_key) is None

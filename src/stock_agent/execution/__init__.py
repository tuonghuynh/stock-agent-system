"""Paper-only broker execution boundary."""

from stock_agent.execution.broker import BrokerAdapter, BrokerOrder
from stock_agent.execution.fake_broker import FakeBroker
from stock_agent.execution.identity import derive_client_order_id, derive_idempotency_key
from stock_agent.execution.service import ExecutionService
from stock_agent.execution.store import InMemoryExecutionStore, StoredExecution

__all__ = [
    "BrokerAdapter",
    "BrokerOrder",
    "ExecutionService",
    "FakeBroker",
    "InMemoryExecutionStore",
    "StoredExecution",
    "derive_client_order_id",
    "derive_idempotency_key",
]

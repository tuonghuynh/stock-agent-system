"""Atomic execution persistence abstractions."""

from dataclasses import dataclass
from threading import RLock
from uuid import UUID

from stock_agent.domain.models import TradeIntent
from stock_agent.execution.broker import BrokerOrder


@dataclass(frozen=True, slots=True)
class StoredExecution:
    intent: TradeIntent
    order: BrokerOrder | None = None


@dataclass(frozen=True, slots=True)
class CreateResult:
    execution: StoredExecution
    created: bool


class InMemoryExecutionStore:
    """Atomic deterministic store for tests; SQL storage supplies equivalent uniqueness."""

    def __init__(self) -> None:
        self._lock = RLock()
        self._by_key: dict[str, StoredExecution] = {}
        self._keys_by_intent: dict[UUID, str] = {}

    def create_if_absent(self, intent: TradeIntent) -> CreateResult:
        with self._lock:
            existing = self._by_key.get(intent.idempotency_key)
            if existing is not None:
                return CreateResult(existing, created=False)
            prior_key = self._keys_by_intent.get(intent.intent_id)
            if prior_key is not None:
                raise ValueError("intent ID already exists with another idempotency key")
            created = StoredExecution(intent=intent)
            self._by_key[intent.idempotency_key] = created
            self._keys_by_intent[intent.intent_id] = intent.idempotency_key
            return CreateResult(created, created=True)

    def update_intent(self, intent: TradeIntent) -> StoredExecution:
        with self._lock:
            key = self._keys_by_intent.get(intent.intent_id)
            if key != intent.idempotency_key:
                raise ValueError("intent must be persisted before it is updated")
            current = self._by_key[key]
            updated = StoredExecution(intent=intent, order=current.order)
            self._by_key[key] = updated
            return updated

    def attach_order(self, intent_id: UUID, order: BrokerOrder) -> StoredExecution:
        with self._lock:
            key = self._keys_by_intent.get(intent_id)
            if key is None:
                raise ValueError("intent must be persisted before a broker order")
            current = self._by_key[key]
            updated = StoredExecution(intent=current.intent, order=order)
            self._by_key[key] = updated
            return updated

    def find_by_idempotency_key(self, key: str) -> StoredExecution | None:
        with self._lock:
            return self._by_key.get(key)

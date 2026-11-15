"""Persist-before-side-effect paper execution service."""

from collections.abc import Callable
from datetime import datetime
from threading import RLock
from typing import Protocol

from stock_agent.domain.models import (
    IntentStatus,
    OrderType,
    TimeInForce,
    TradeEnvironment,
    TradeIntent,
)
from stock_agent.execution.broker import BrokerAdapter, SubmissionTimeout
from stock_agent.execution.identity import derive_client_order_id
from stock_agent.execution.state_machine import require_transition
from stock_agent.execution.store import InMemoryExecutionStore, StoredExecution


class SubmissionGate(Protocol):
    @property
    def paused(self) -> bool: ...


class ExecutionService:
    def __init__(
        self,
        store: InMemoryExecutionStore,
        broker: BrokerAdapter,
        now: Callable[[], datetime],
        submission_gate: SubmissionGate | None = None,
    ) -> None:
        self._store = store
        self._broker = broker
        self._now = now
        self._submission_gate = submission_gate
        self._claim_lock = RLock()

    def submit(self, requested: TradeIntent) -> StoredExecution:
        if self._submission_gate is not None and self._submission_gate.paused:
            raise RuntimeError("new submissions are paused pending reconciliation")
        self._require_executable(requested)
        # This lock makes the in-memory claim and result publication atomic. The SQL
        # implementation uses a unique key plus row locking for cross-process safety.
        with self._claim_lock:
            claim = self._store.create_if_absent(requested)
            if not claim.created:
                return claim.execution
            if requested.expires_at <= self._now():
                return self._transition(requested, IntentStatus.EXPIRED)

            submitting = self._transition(requested, IntentStatus.SUBMITTING).intent
            try:
                order = self._broker.submit(
                    submitting, derive_client_order_id(submitting.intent_id)
                )
            except SubmissionTimeout:
                return self._transition(submitting, IntentStatus.UNKNOWN)
            submitted = self._transition(submitting, IntentStatus.SUBMITTED).intent
            return self._store.attach_order(submitted.intent_id, order)

    def _transition(self, intent: TradeIntent, target: IntentStatus) -> StoredExecution:
        require_transition(intent.status, target)
        return self._store.update_intent(intent.model_copy(update={"status": target}))

    @staticmethod
    def _require_executable(intent: TradeIntent) -> None:
        if (
            intent.environment is not TradeEnvironment.PAPER
            or intent.order_type is not OrderType.LIMIT
            or intent.time_in_force is not TimeInForce.DAY
        ):
            raise ValueError("only PAPER LIMIT DAY intents are executable")
        if intent.status is not IntentStatus.RESERVED:
            raise ValueError("only transactionally reserved intents may be submitted")

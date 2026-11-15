"""Append-only audit persistence boundary."""

from threading import RLock
from typing import Protocol
from uuid import UUID

from stock_agent.domain.models import AuditEvent
from stock_agent.observability.redaction import assert_redacted


class AuditIntegrityError(ValueError):
    """Raised when an append would mutate or duplicate audit history."""


class AuditSink(Protocol):
    def append(self, event: AuditEvent) -> None: ...

    def events_for_trace(self, trace_id: str) -> tuple[AuditEvent, ...]: ...


class AppendOnlyAuditLog:
    """Thread-safe development adapter with append-only production semantics."""

    def __init__(self) -> None:
        self._events: list[AuditEvent] = []
        self._by_id: dict[UUID, AuditEvent] = {}
        self._lock = RLock()

    def append(self, event: AuditEvent) -> None:
        assert_redacted(event.redacted_metadata)
        with self._lock:
            if event.event_id in self._by_id:
                raise AuditIntegrityError(f"event {event.event_id} already exists")
            self._events.append(event)
            self._by_id[event.event_id] = event

    def events_for_trace(self, trace_id: str) -> tuple[AuditEvent, ...]:
        with self._lock:
            return tuple(event for event in self._events if event.trace_id == trace_id)

    def all_events(self) -> tuple[AuditEvent, ...]:
        with self._lock:
            return tuple(self._events)

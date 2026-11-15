"""Database-style lease claiming implemented deterministically for local tests."""

from datetime import datetime, timedelta
from threading import RLock
from uuid import UUID

from stock_agent.reliability.models import WorkClaim, WorkStatus


class InMemoryWorkClaimStore:
    """Mirrors a row-lock/skip-locked work table without introducing a queue."""

    def __init__(self) -> None:
        self._items: dict[UUID, WorkClaim] = {}
        self._lock = RLock()

    def enqueue(self, item: WorkClaim) -> WorkClaim:
        if item.status is not WorkStatus.PENDING:
            raise ValueError("new work must be pending")
        with self._lock:
            existing = self._items.get(item.work_id)
            if existing is not None:
                if existing.kind != item.kind or existing.reference != item.reference:
                    raise ValueError("work identity is immutable")
                return existing
            self._items[item.work_id] = item
            return item

    def claim(
        self, *, worker: str, now: datetime, lease_duration: timedelta
    ) -> WorkClaim | None:
        if not worker.strip() or lease_duration <= timedelta(0):
            raise ValueError("worker and positive lease are required")
        with self._lock:
            for work_id in sorted(self._items, key=str):
                item = self._items[work_id]
                available = item.status is WorkStatus.PENDING or (
                    item.status is WorkStatus.CLAIMED
                    and item.lease_expires_at is not None
                    and item.lease_expires_at <= now
                )
                if not available:
                    continue
                claimed = item.model_copy(
                    update={
                        "status": WorkStatus.CLAIMED,
                        "owner": worker,
                        "lease_expires_at": now + lease_duration,
                        "attempts": item.attempts + 1,
                        "failure_code": None,
                    }
                )
                self._items[work_id] = claimed
                return claimed
            return None

    def heartbeat(
        self, *, work_id: UUID, worker: str, now: datetime, lease_duration: timedelta
    ) -> WorkClaim:
        if lease_duration <= timedelta(0):
            raise ValueError("lease duration must be positive")
        with self._lock:
            item = self._owned_active(work_id, worker, now)
            updated = item.model_copy(update={"lease_expires_at": now + lease_duration})
            self._items[work_id] = updated
            return updated

    def complete(self, *, work_id: UUID, worker: str, now: datetime) -> WorkClaim:
        with self._lock:
            item = self._owned_active(work_id, worker, now)
            completed = item.model_copy(
                update={
                    "status": WorkStatus.COMPLETED,
                    "owner": None,
                    "lease_expires_at": None,
                    "completed_at": now,
                }
            )
            self._items[work_id] = completed
            return completed

    def release_retryable(self, *, work_id: UUID, worker: str, now: datetime) -> WorkClaim:
        with self._lock:
            item = self._owned_active(work_id, worker, now)
            pending = item.model_copy(
                update={
                    "status": WorkStatus.PENDING,
                    "owner": None,
                    "lease_expires_at": None,
                }
            )
            self._items[work_id] = pending
            return pending

    def fail_terminal(
        self, *, work_id: UUID, worker: str, now: datetime, failure_code: str
    ) -> WorkClaim:
        if not failure_code.strip():
            raise ValueError("failure code is required")
        with self._lock:
            item = self._owned_active(work_id, worker, now)
            terminal = item.model_copy(
                update={
                    "status": WorkStatus.TERMINAL,
                    "owner": None,
                    "lease_expires_at": None,
                    "failure_code": failure_code,
                }
            )
            self._items[work_id] = terminal
            return terminal

    def get(self, work_id: UUID) -> WorkClaim | None:
        with self._lock:
            return self._items.get(work_id)

    def _owned_active(self, work_id: UUID, worker: str, now: datetime) -> WorkClaim:
        item = self._items.get(work_id)
        if item is None:
            raise KeyError(work_id)
        if item.status is not WorkStatus.CLAIMED or item.owner != worker:
            raise PermissionError("worker does not own active claim")
        if item.lease_expires_at is None or item.lease_expires_at <= now:
            raise PermissionError("work lease has expired")
        return item

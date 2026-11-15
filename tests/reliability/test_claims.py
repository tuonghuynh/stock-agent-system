from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest

from stock_agent.reliability import InMemoryWorkClaimStore, WorkClaim, WorkStatus

NOW = datetime(2026, 11, 14, 20, tzinfo=UTC)
WORK_ID = UUID("10000000-0000-0000-0000-000000000001")


def pending() -> WorkClaim:
    return WorkClaim(work_id=WORK_ID, kind="COORDINATOR", reference="run:1")


def test_concurrent_claiming_has_exactly_one_owner() -> None:
    store = InMemoryWorkClaimStore()
    store.enqueue(pending())

    def claim(worker: str) -> WorkClaim | None:
        return store.claim(worker=worker, now=NOW, lease_duration=timedelta(seconds=30))

    with ThreadPoolExecutor(max_workers=8) as executor:
        claims = list(executor.map(claim, (f"worker-{index}" for index in range(32))))
    winners = [item for item in claims if item is not None]
    assert len(winners) == 1
    assert winners[0].status is WorkStatus.CLAIMED


def test_expired_lease_is_reclaimed_after_restart_without_touching_completed_work() -> None:
    store = InMemoryWorkClaimStore()
    store.enqueue(pending())
    first = store.claim(worker="old", now=NOW, lease_duration=timedelta(seconds=5))
    assert first is not None and first.attempts == 1
    assert store.claim(worker="new", now=NOW, lease_duration=timedelta(seconds=5)) is None

    reclaimed = store.claim(
        worker="new", now=NOW + timedelta(seconds=5), lease_duration=timedelta(seconds=5)
    )
    assert reclaimed is not None and reclaimed.owner == "new" and reclaimed.attempts == 2
    completed = store.complete(
        work_id=WORK_ID, worker="new", now=NOW + timedelta(seconds=6)
    )
    assert completed.status is WorkStatus.COMPLETED
    assert store.claim(
        worker="third", now=NOW + timedelta(minutes=1), lease_duration=timedelta(seconds=5)
    ) is None
    assert store.enqueue(pending()) == completed


def test_heartbeat_and_ownership_are_enforced() -> None:
    store = InMemoryWorkClaimStore()
    store.enqueue(pending())
    assert store.claim(worker="owner", now=NOW, lease_duration=timedelta(seconds=5))
    extended = store.heartbeat(
        work_id=WORK_ID,
        worker="owner",
        now=NOW + timedelta(seconds=2),
        lease_duration=timedelta(seconds=10),
    )
    assert extended.lease_expires_at == NOW + timedelta(seconds=12)
    with pytest.raises(PermissionError):
        store.complete(work_id=WORK_ID, worker="other", now=NOW + timedelta(seconds=3))

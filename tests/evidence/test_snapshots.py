from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from pydantic import HttpUrl

from stock_agent.domain.models import FreshnessStatus, TrustClass
from stock_agent.evidence import (
    Availability,
    EvidenceMaterial,
    EvidenceSnapshotBuilder,
    FutureEvidenceError,
    InMemoryEvidenceSnapshotRepository,
)

AS_OF = datetime(2026, 11, 14, 20, tzinfo=UTC)
HASH_A = "a" * 64
HASH_B = "b" * 64


def material(
    evidence_id: UUID,
    *,
    source_time: datetime,
    content_hash: str = HASH_A,
    maximum_age: timedelta = timedelta(minutes=5),
    availability: Availability = Availability.AVAILABLE,
    conflicts: tuple[str, ...] = (),
) -> EvidenceMaterial:
    return EvidenceMaterial(
        evidence_id=evidence_id,
        type="QUOTE",
        content_reference="immutable://quote/1",
        source_id="approved-feed",
        source_uri=HttpUrl("https://example.test/quote"),
        publisher="Approved Provider",
        source_timestamp=source_time,
        retrieved_at=source_time,
        content_hash=content_hash,
        trust_class=TrustClass.APPROVED_SECONDARY,
        maximum_age=maximum_age,
        availability=availability,
        conflicts=conflicts,
    )


def test_dat001_snapshot_hash_is_canonical_and_input_order_independent() -> None:
    builder = EvidenceSnapshotBuilder()
    run_id, snapshot_id = uuid4(), uuid4()
    first = material(UUID(int=1), source_time=AS_OF - timedelta(seconds=30))
    second = material(UUID(int=2), source_time=AS_OF - timedelta(seconds=20), content_hash=HASH_B)

    ordered = builder.build(
        snapshot_id=snapshot_id, run_id=run_id, as_of=AS_OF, materials=(first, second)
    )
    reversed_snapshot = builder.build(
        snapshot_id=snapshot_id, run_id=run_id, as_of=AS_OF, materials=(second, first)
    )

    assert ordered == reversed_snapshot
    assert len(ordered.content_hash) == 64
    with pytest.raises(TypeError):
        ordered.entries[0] = ordered.entries[1]  # type: ignore[index]


def test_dat004_explicitly_classifies_unavailable_stale_and_conflicting() -> None:
    snapshot = EvidenceSnapshotBuilder().build(
        snapshot_id=uuid4(),
        run_id=uuid4(),
        as_of=AS_OF,
        materials=(
            material(
                UUID(int=1),
                source_time=AS_OF - timedelta(seconds=1),
                availability=Availability.UNAVAILABLE,
            ),
            material(
                UUID(int=2),
                source_time=AS_OF - timedelta(days=2),
                maximum_age=timedelta(days=1),
            ),
            material(
                UUID(int=3),
                source_time=AS_OF,
                conflicts=("provider values disagree",),
            ),
        ),
    )

    assert tuple(entry.freshness_status for entry in snapshot.entries) == (
        FreshnessStatus.UNAVAILABLE,
        FreshnessStatus.STALE,
        FreshnessStatus.CONFLICTING,
    )
    assert snapshot.entries[-1].conflicts == ("provider values disagree",)


def test_at029_rejects_future_source_and_retrieval_timestamps() -> None:
    builder = EvidenceSnapshotBuilder()
    future_source = material(uuid4(), source_time=AS_OF + timedelta(microseconds=1))
    with pytest.raises(FutureEvidenceError, match="newer than snapshot"):
        builder.build(snapshot_id=uuid4(), run_id=uuid4(), as_of=AS_OF, materials=(future_source,))

    future_retrieval = EvidenceMaterial(
        evidence_id=uuid4(),
        type="FILING",
        content_reference="immutable://filing/1",
        source_id="sec",
        source_uri=None,
        publisher="SEC",
        source_timestamp=AS_OF - timedelta(seconds=1),
        retrieved_at=AS_OF + timedelta(seconds=1),
        content_hash=HASH_A,
        trust_class=TrustClass.PRIMARY,
        maximum_age=timedelta(days=1),
    )
    with pytest.raises(FutureEvidenceError, match="newer than snapshot"):
        builder.build(
            snapshot_id=uuid4(), run_id=uuid4(), as_of=AS_OF, materials=(future_retrieval,)
        )


def test_dat001_repository_is_idempotent_and_rejects_replacement() -> None:
    builder = EvidenceSnapshotBuilder()
    repository = InMemoryEvidenceSnapshotRepository()
    run_id = uuid4()
    original = builder.build(
        snapshot_id=uuid4(),
        run_id=run_id,
        as_of=AS_OF,
        materials=(material(uuid4(), source_time=AS_OF),),
    )
    replacement = builder.build(
        snapshot_id=uuid4(),
        run_id=run_id,
        as_of=AS_OF,
        materials=(material(uuid4(), source_time=AS_OF, content_hash=HASH_B),),
    )

    assert repository.save(original) is original
    assert repository.save(original) is original
    with pytest.raises(ValueError, match="immutable evidence snapshot"):
        repository.save(replacement)
    assert repository.find_by_run_id(run_id) == original

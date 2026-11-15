from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum
from threading import RLock
from typing import Protocol
from uuid import UUID

from pydantic import HttpUrl

from stock_agent.domain.models import (
    EvidenceEntry,
    EvidenceSnapshot,
    FreshnessStatus,
    TrustClass,
)


class Availability(StrEnum):
    AVAILABLE = "AVAILABLE"
    UNAVAILABLE = "UNAVAILABLE"


@dataclass(frozen=True, slots=True)
class EvidenceMaterial:
    evidence_id: UUID
    type: str
    content_reference: str
    source_id: str
    source_uri: HttpUrl | None
    publisher: str
    source_timestamp: datetime
    retrieved_at: datetime
    content_hash: str
    trust_class: TrustClass
    maximum_age: timedelta
    availability: Availability = Availability.AVAILABLE
    conflicts: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for name in ("type", "content_reference", "source_id", "publisher"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} must not be blank")
        invalid_hash = len(self.content_hash) != 64 or any(
            c not in "0123456789abcdef" for c in self.content_hash
        )
        if invalid_hash:
            raise ValueError("content_hash must be lowercase SHA-256 hexadecimal")
        if self.maximum_age < timedelta(0):
            raise ValueError("maximum_age must not be negative")
        _require_aware(self.source_timestamp, "source_timestamp")
        _require_aware(self.retrieved_at, "retrieved_at")


class FutureEvidenceError(ValueError):
    pass


class EvidenceSnapshotBuilder:
    """Builds immutable, canonical point-in-time snapshots from trusted metadata."""

    def build(
        self,
        *,
        snapshot_id: UUID,
        run_id: UUID,
        as_of: datetime,
        materials: Iterable[EvidenceMaterial],
    ) -> EvidenceSnapshot:
        _require_aware(as_of, "as_of")
        material_list = tuple(materials)
        if not material_list:
            raise ValueError("materials must not be empty")
        entries = tuple(
            sorted(
                (self._entry(material, as_of) for material in material_list),
                key=lambda entry: entry.evidence_id.hex,
            )
        )
        canonical = {
            "as_of": as_of.isoformat(),
            "entries": [entry.model_dump(mode="json") for entry in entries],
            "run_id": str(run_id),
        }
        content_hash = hashlib.sha256(
            json.dumps(canonical, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        return EvidenceSnapshot(
            snapshot_id=snapshot_id,
            run_id=run_id,
            as_of=as_of,
            entries=entries,
            content_hash=content_hash,
        )

    @staticmethod
    def _entry(material: EvidenceMaterial, as_of: datetime) -> EvidenceEntry:
        if material.source_timestamp > as_of or material.retrieved_at > as_of:
            raise FutureEvidenceError(
                f"evidence {material.evidence_id} is newer than snapshot as_of"
            )
        if material.availability is Availability.UNAVAILABLE:
            freshness = FreshnessStatus.UNAVAILABLE
        elif material.conflicts:
            freshness = FreshnessStatus.CONFLICTING
        elif material.source_timestamp + material.maximum_age < as_of:
            freshness = FreshnessStatus.STALE
        else:
            freshness = FreshnessStatus.FRESH
        return EvidenceEntry(
            evidence_id=material.evidence_id,
            type=material.type,
            content_reference=material.content_reference,
            source_id=material.source_id,
            source_uri=material.source_uri,
            publisher=material.publisher,
            source_timestamp=material.source_timestamp,
            retrieved_at=material.retrieved_at,
            content_hash=material.content_hash,
            freshness_status=freshness,
            trust_class=material.trust_class,
            conflicts=material.conflicts,
        )


class EvidenceSnapshotRepository(Protocol):
    def save(self, snapshot: EvidenceSnapshot) -> EvidenceSnapshot: ...

    def find_by_run_id(self, run_id: UUID) -> EvidenceSnapshot | None: ...


class InMemoryEvidenceSnapshotRepository:
    """Thread-safe test adapter enforcing one immutable snapshot per decision run."""

    def __init__(self) -> None:
        self._by_run: dict[UUID, EvidenceSnapshot] = {}
        self._lock = RLock()

    def save(self, snapshot: EvidenceSnapshot) -> EvidenceSnapshot:
        with self._lock:
            existing = self._by_run.get(snapshot.run_id)
            if existing is None:
                self._by_run[snapshot.run_id] = snapshot
                return snapshot
            if existing == snapshot:
                return existing
            raise ValueError(
                f"immutable evidence snapshot already exists for run {snapshot.run_id}"
            )

    def find_by_run_id(self, run_id: UUID) -> EvidenceSnapshot | None:
        with self._lock:
            return self._by_run.get(run_id)


def _require_aware(value: datetime, field: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field} must be timezone-aware")

from threading import RLock
from uuid import UUID

from stock_agent.coordinator.models import RunRecord
from stock_agent.domain.models import RunManifest


class InMemoryRunStore:
    def __init__(self) -> None:
        self._records: dict[UUID, RunRecord] = {}
        self._lock = RLock()

    def create_or_get(self, manifest: RunManifest) -> RunRecord:
        with self._lock:
            existing = self._records.get(manifest.run_id)
            if existing is None:
                existing = RunRecord(manifest=manifest)
                self._records[manifest.run_id] = existing
            elif existing.manifest != manifest:
                raise ValueError(
                    "a run manifest is immutable; changed objective requires a new run"
                )
            return existing

    def save(self, record: RunRecord) -> RunRecord:
        with self._lock:
            current = self._records.get(record.manifest.run_id)
            if current is None:
                raise ValueError("run must be created before checkpointing")
            if current.manifest != record.manifest:
                raise ValueError("run manifest cannot be mutated")
            if record.checkpoints[: len(current.checkpoints)] != current.checkpoints:
                raise ValueError("checkpoint history is append-only")
            self._records[record.manifest.run_id] = record
            return record

    def get(self, run_id: UUID) -> RunRecord | None:
        with self._lock:
            return self._records.get(run_id)

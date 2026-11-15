"""Immutable trace and release-version propagation."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID, uuid4


@dataclass(frozen=True, slots=True)
class VersionContext:
    release: str
    policy: str
    workflow: str
    data: str
    model: str
    prompt: str
    tools: str

    def __post_init__(self) -> None:
        for name in self.__dataclass_fields__:
            value = getattr(self, name)
            if not value.strip():
                raise ValueError(f"{name} version must not be blank")

    def audit_metadata(self) -> dict[str, str]:
        return {
            "release_version": self.release,
            "policy_version": self.policy,
            "workflow_version": self.workflow,
            "data_version": self.data,
            "model_version": self.model,
            "prompt_version": self.prompt,
            "tool_version": self.tools,
        }


@dataclass(frozen=True, slots=True)
class TraceContext:
    trace_id: str
    span_id: UUID
    run_id: UUID
    versions: VersionContext
    parent_span_id: UUID | None = None

    def __post_init__(self) -> None:
        if not self.trace_id.strip():
            raise ValueError("trace_id must not be blank")

    @classmethod
    def start(cls, *, run_id: UUID, versions: VersionContext, trace_id: str) -> TraceContext:
        return cls(trace_id=trace_id, span_id=uuid4(), run_id=run_id, versions=versions)

    def child(self) -> TraceContext:
        return TraceContext(
            trace_id=self.trace_id,
            span_id=uuid4(),
            parent_span_id=self.span_id,
            run_id=self.run_id,
            versions=self.versions,
        )

    def audit_metadata(self) -> dict[str, str]:
        metadata = self.versions.audit_metadata()
        metadata.update(
            {
                "span_id": str(self.span_id),
                "parent_span_id": str(self.parent_span_id) if self.parent_span_id else "ROOT",
            }
        )
        return metadata

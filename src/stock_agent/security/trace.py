"""Trace completeness and sensitive-metadata assertions."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass

from stock_agent.domain.models import AuditEvent
from stock_agent.observability.redaction import redact


@dataclass(frozen=True, slots=True)
class SecureTraceAssertion:
    trace_id: str
    components: tuple[str, ...]
    references: frozenset[str]


_REQUIRED_COMPONENTS = frozenset({"evidence", "agents", "risk", "execution", "fills"})


def assert_secure_trace(
    events: Iterable[AuditEvent], *, configured_sensitive_values: Iterable[str] = ()
) -> SecureTraceAssertion:
    recorded = tuple(events)
    if not recorded:
        raise ValueError("trace must contain audit events")
    trace_ids = {event.trace_id for event in recorded}
    if len(trace_ids) != 1:
        raise ValueError("decision lifecycle must use one trace ID")
    components = tuple(event.component for event in recorded)
    missing = _REQUIRED_COMPONENTS - set(components)
    if missing:
        raise ValueError("trace is missing required lifecycle components")
    for event in recorded:
        metadata: Mapping[str, object] = event.redacted_metadata
        if redact(metadata) != dict(metadata):
            raise ValueError("trace contains unredacted sensitive metadata")
        rendered = event.model_dump_json().lower()
        for sensitive in configured_sensitive_values:
            if sensitive and sensitive.lower() in rendered:
                raise ValueError("trace contains a configured sensitive value")
    references = frozenset(
        reference
        for event in recorded
        for reference in (*event.input_references, *event.output_references)
    )
    return SecureTraceAssertion(
        trace_id=next(iter(trace_ids)), components=components, references=references
    )

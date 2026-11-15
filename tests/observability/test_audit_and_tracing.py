from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError

from stock_agent.domain.models import AuditEvent
from stock_agent.observability import (
    AppendOnlyAuditLog,
    AuditIntegrityError,
    TraceContext,
    VersionContext,
)

NOW = datetime(2026, 11, 14, 20, tzinfo=UTC)


def versions() -> VersionContext:
    return VersionContext(
        release="release-1",
        policy="1",
        workflow="workflow-1",
        data="snapshot-sha256",
        model="fake-model-1",
        prompt="research-1",
        tools="readonly-1",
    )


def event(
    context: TraceContext,
    *,
    event_id: UUID | None = None,
    component: str = "evidence",
    inputs: tuple[str, ...] = (),
    outputs: tuple[str, ...] = (),
) -> AuditEvent:
    return AuditEvent(
        event_id=event_id or uuid4(),
        trace_id=context.trace_id,
        run_id=context.run_id,
        intent_id=None,
        event_type="STEP_COMPLETED",
        component=component,
        occurred_at=NOW,
        actor_type="DETERMINISTIC_SERVICE",
        actor_version="1",
        input_references=inputs,
        output_references=outputs,
        duration_ms=2,
        token_count=0,
        estimated_cost=Decimal(0),
        redacted_metadata=context.audit_metadata(),
    )


def test_audit_is_append_only_and_events_are_immutable() -> None:
    context = TraceContext.start(run_id=uuid4(), versions=versions(), trace_id="trace-1")
    audit = AppendOnlyAuditLog()
    original = event(context)
    audit.append(original)

    with pytest.raises(AuditIntegrityError, match="already exists"):
        audit.append(original)
    with pytest.raises(ValidationError):
        original.component = "mutated"  # type: ignore[misc]

    assert audit.all_events() == (original,)


def test_at028_one_trace_links_full_decision_lifecycle_and_versions() -> None:
    root = TraceContext.start(run_id=uuid4(), versions=versions(), trace_id="trace-lifecycle")
    audit = AppendOnlyAuditLog()
    stages = (
        ("evidence", (), ("evidence:snapshot-1",)),
        ("agents", ("evidence:snapshot-1",), ("recommendation:1",)),
        ("risk", ("recommendation:1",), ("risk-decision:1",)),
        ("execution", ("risk-decision:1",), ("intent:1", "order:1")),
        ("fills", ("order:1",), ("fill:1",)),
    )
    parent = root
    for component, inputs, outputs in stages:
        child = parent.child()
        audit.append(event(child, component=component, inputs=inputs, outputs=outputs))
        assert child.parent_span_id == parent.span_id
        assert child.trace_id == root.trace_id
        parent = child

    recorded = audit.events_for_trace(root.trace_id)
    assert tuple(item.component for item in recorded) == tuple(stage[0] for stage in stages)
    references = {
        reference
        for item in recorded
        for reference in (*item.input_references, *item.output_references)
    }
    assert references >= {
        "evidence:snapshot-1",
        "recommendation:1",
        "risk-decision:1",
        "intent:1",
        "order:1",
        "fill:1",
    }
    assert all(item.redacted_metadata["policy_version"] == "1" for item in recorded)
    assert all(item.redacted_metadata["workflow_version"] == "workflow-1" for item in recorded)


def test_audit_rejects_unredacted_metadata() -> None:
    context = TraceContext.start(run_id=uuid4(), versions=versions(), trace_id="trace-secret")
    unsafe = event(context).model_copy(update={"redacted_metadata": {"api_key": "not-safe"}})
    with pytest.raises(ValueError, match="sensitive"):
        AppendOnlyAuditLog().append(unsafe)

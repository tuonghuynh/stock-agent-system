from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

import pytest

from stock_agent.domain.models import AuditEvent
from stock_agent.observability.redaction import REDACTED, redact
from stock_agent.security import assert_secure_trace

NOW = datetime(2026, 11, 14, 20, tzinfo=UTC)


def event(
    trace_id: str,
    component: str,
    inputs: tuple[str, ...],
    outputs: tuple[str, ...],
) -> AuditEvent:
    return AuditEvent(
        event_id=uuid4(),
        trace_id=trace_id,
        run_id=uuid4(),
        intent_id=None,
        event_type="STEP_COMPLETED",
        component=component,
        occurred_at=NOW,
        actor_type="DETERMINISTIC_SERVICE",
        actor_version="1",
        input_references=inputs,
        output_references=outputs,
        duration_ms=1,
        token_count=0,
        estimated_cost=Decimal(0),
        redacted_metadata={"policy_version": "1", "account_id": REDACTED},
    )


def lifecycle(trace_id: str = "trace-security") -> tuple[AuditEvent, ...]:
    return (
        event(trace_id, "evidence", (), ("evidence:snapshot",)),
        event(trace_id, "agents", ("evidence:snapshot",), ("recommendation:1",)),
        event(trace_id, "risk", ("recommendation:1",), ("risk:1",)),
        event(trace_id, "execution", ("risk:1",), ("intent:1", "order:1")),
        event(trace_id, "fills", ("order:1",), ("fill:1",)),
    )


def test_at027_recursive_redaction_covers_prompt_credentials_accounts_and_personal_data() -> None:
    sensitive_marker = "configured-sensitive-marker-8237"
    unsafe = {
        "authorization": f"Bearer {sensitive_marker}",
        "raw_prompt": "private input",
        "account_number": "account-identifier-8237",
        "nested": {"personal_financial_data": "private"},
    }
    safe = redact(unsafe)
    rendered = repr(safe)
    assert safe == {
        "authorization": REDACTED,
        "raw_prompt": REDACTED,
        "account_number": REDACTED,
        "nested": {"personal_financial_data": REDACTED},
    }
    assert sensitive_marker not in rendered
    assert "private input" not in rendered


def test_at028_secure_trace_links_the_complete_lifecycle() -> None:
    checked = assert_secure_trace(lifecycle(), configured_sensitive_values=("not-present",))
    assert checked.trace_id == "trace-security"
    assert checked.references >= {
        "evidence:snapshot",
        "recommendation:1",
        "risk:1",
        "intent:1",
        "order:1",
        "fill:1",
    }


def test_trace_rejects_multiple_ids_missing_stage_and_sensitive_metadata() -> None:
    events = list(lifecycle())
    events[-1] = event("trace-other", "fills", ("order:1",), ("fill:1",))
    with pytest.raises(ValueError, match="one trace"):
        assert_secure_trace(events)
    with pytest.raises(ValueError, match="missing"):
        assert_secure_trace(lifecycle()[:-1])

    marker = "configured-sensitive-marker-9238"
    unsafe = lifecycle()[0].model_copy(
        update={"redacted_metadata": {"diagnostic": marker}}
    )
    with pytest.raises(ValueError, match="configured sensitive"):
        assert_secure_trace((unsafe, *lifecycle()[1:]), configured_sensitive_values=(marker,))

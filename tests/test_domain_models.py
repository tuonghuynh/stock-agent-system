from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest
from pydantic import ValidationError

from stock_agent.domain.models import RunManifest, RunStatus


def manifest_data() -> dict[str, object]:
    now = datetime(2026, 11, 14, 18, tzinfo=UTC)
    return {
        "run_id": uuid4(),
        "trace_id": "trace-1",
        "objective": "evaluate",
        "symbols": ("AAPL",),
        "horizon": "20d",
        "as_of": now,
        "policy_version": "1",
        "release_version": "release-v1",
        "workflow_version": "workflow-v1",
        "data_snapshot_id": uuid4(),
        "model_versions": {"research": "fake-v1"},
        "prompt_versions": {"research": "research-v1"},
        "tool_versions": {"evidence": "evidence-v1"},
        "deadline": now + timedelta(minutes=5),
        "max_model_calls": 4,
        "max_tool_calls": 10,
        "max_tokens": 20_000,
        "max_cost": Decimal("1.00"),
        "allowed_actions": ("RECOMMEND",),
        "prohibited_actions": ("BROKER_ACCESS",),
        "status": RunStatus.CREATED,
    }


def test_at002_manifest_is_strict_frozen_and_versioned() -> None:
    manifest = RunManifest.model_validate(manifest_data())
    assert manifest.policy_version == "1"
    assert manifest.release_version == "release-v1"
    with pytest.raises(ValidationError):
        RunManifest.model_validate({**manifest_data(), "unknown": True})
    with pytest.raises(ValidationError):
        manifest.status = RunStatus.RUNNING  # type: ignore[misc]


def test_manifest_rejects_deadline_before_snapshot() -> None:
    data = manifest_data()
    data["deadline"] = data["as_of"]
    with pytest.raises(ValidationError, match="deadline"):
        RunManifest.model_validate(data)

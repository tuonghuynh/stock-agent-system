import pytest
from pydantic import ValidationError

from stock_agent.policy import load_policy
from stock_agent.policy.models import PolicyDocument


def test_at001_policy_v1_loads_and_is_paper_only() -> None:
    policy = load_policy("POLICY_V1.yaml")
    assert policy.policy_id == "personal-growth-policy"
    assert policy.version == 1
    assert policy.execution.environment == "PAPER"
    assert policy.execution.live_trading_enabled is False
    assert policy.decision.minimum_executable_confidence == 65


def test_policy_rejects_live_mode() -> None:
    policy = load_policy("POLICY_V1.yaml")
    data = policy.model_dump(mode="python")
    data["execution"]["live_trading_enabled"] = True
    with pytest.raises(ValidationError, match="PAPER, LIMIT, DAY"):
        PolicyDocument.model_validate(data)

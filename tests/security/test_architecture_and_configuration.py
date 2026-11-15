from pathlib import Path

import pytest
from pydantic import ValidationError

from stock_agent.security import RuntimeSecurityConfig, inspect_agent_boundary
from stock_agent.settings import BrokerMode


def test_at026_agent_packages_have_no_broker_credential_or_policy_write_capability() -> None:
    assert inspect_agent_boundary(Path("src/stock_agent/agents")) == ()


def test_architecture_scanner_detects_prohibited_capability(tmp_path: Path) -> None:
    unsafe = tmp_path / "agent.py"
    unsafe.write_text(
        "from stock_agent.execution import BrokerAdapter\napi_key = 'not-a-value'\n",
        encoding="utf-8",
    )
    violations = inspect_agent_boundary(tmp_path)
    assert {item.capability for item in violations} >= {
        "stock_agent.execution",
        "BrokerAdapter",
        "api_key",
    }


def test_at025_fake_and_canonical_paper_configuration_are_allowed() -> None:
    fake = RuntimeSecurityConfig(
        broker_mode=BrokerMode.FAKE,
        live_trading_enabled=False,
        credentials_source="environment",
    )
    paper = RuntimeSecurityConfig(
        broker_mode=BrokerMode.ALPACA_PAPER,
        live_trading_enabled=False,
        broker_endpoint="https://paper-api.alpaca.markets",
        credentials_source="environment",
    )
    assert fake.broker_endpoint is None
    assert paper.broker_endpoint == "https://paper-api.alpaca.markets"


@pytest.mark.parametrize(
    "payload",
    [
        {
            "broker_mode": BrokerMode.FAKE,
            "live_trading_enabled": True,
            "credentials_source": "environment",
        },
        {
            "broker_mode": BrokerMode.ALPACA_PAPER,
            "live_trading_enabled": False,
            "broker_endpoint": "https://api.alpaca.markets",
            "credentials_source": "environment",
        },
        {
            "broker_mode": BrokerMode.ALPACA_PAPER,
            "live_trading_enabled": False,
            "broker_endpoint": "https://example.invalid",
            "credentials_source": "environment",
        },
        {
            "broker_mode": BrokerMode.FAKE,
            "live_trading_enabled": False,
            "credentials_source": "prompt",
        },
    ],
)
def test_at025_live_or_prompt_credential_configuration_is_rejected(
    payload: dict[str, object],
) -> None:
    with pytest.raises(ValidationError):
        RuntimeSecurityConfig.model_validate(payload, strict=True)

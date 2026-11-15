import pytest
from pydantic import ValidationError

from stock_agent.settings import Settings


def test_live_trading_configuration_is_rejected() -> None:
    with pytest.raises(ValidationError, match="live trading"):
        Settings(live_trading_enabled=True)

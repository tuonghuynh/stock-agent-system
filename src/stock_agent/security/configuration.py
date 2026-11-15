"""Runtime configuration guardrails proving the executable surface is paper-only."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, model_validator

from stock_agent.settings import BrokerMode

PAPER_ENDPOINT = "https://paper-api.alpaca.markets"
_LIVE_ENDPOINT = "https://api.alpaca.markets"


class RuntimeSecurityConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    broker_mode: BrokerMode
    live_trading_enabled: bool
    broker_endpoint: str | None = None
    credentials_source: str = Field(pattern=r"^environment$")

    @model_validator(mode="after")
    def paper_only(self) -> RuntimeSecurityConfig:
        if self.live_trading_enabled:
            raise ValueError("live trading is structurally disabled")
        if self.broker_mode is BrokerMode.ALPACA_PAPER and self.broker_endpoint != PAPER_ENDPOINT:
            raise ValueError("Alpaca mode requires the canonical paper endpoint")
        if self.broker_endpoint == _LIVE_ENDPOINT:
            raise ValueError("live broker endpoint is prohibited")
        if self.broker_mode is BrokerMode.FAKE and self.broker_endpoint is not None:
            raise ValueError("fake broker accepts no credentialed endpoint")
        return self


def validate_runtime_security(config: RuntimeSecurityConfig) -> RuntimeSecurityConfig:
    """Explicit trusted-code validation hook used before application composition."""
    return config

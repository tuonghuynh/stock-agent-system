from enum import StrEnum

from pydantic import AliasChoices, Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class BrokerMode(StrEnum):
    FAKE = "FAKE"
    ALPACA_PAPER = "ALPACA_PAPER"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="forbid")

    environment: str = "development"
    database_url: str = "postgresql+psycopg://stock_agent:stock_agent@localhost/stock_agent"
    broker_mode: BrokerMode = BrokerMode.FAKE
    live_trading_enabled: bool = False
    policy_path: str = "POLICY_V1.yaml"
    release_manifest_path: str = "release-manifest.yaml"
    dev_test_token: str | None = Field(default=None, repr=False)
    git_sha: str = Field(
        default="unknown",
        validation_alias=AliasChoices("GIT_SHA", "RENDER_GIT_COMMIT"),
    )
    require_database_readiness: bool = False

    @model_validator(mode="after")
    def reject_live_trading(self) -> "Settings":
        if self.live_trading_enabled:
            raise ValueError("live trading is not supported")
        return self

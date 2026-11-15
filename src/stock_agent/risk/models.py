from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from stock_agent.policy.models import PolicyDocument


class RiskInputModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class AssetType(StrEnum):
    STOCK = "STOCK"
    ETF = "ETF"


class OrderSide(StrEnum):
    BUY = "BUY"
    SELL = "SELL"


class RiskContext(RiskInputModel):
    recommendation_id: UUID
    account_snapshot_id: UUID
    evaluated_at: datetime
    evidence_timestamp: datetime
    policy: PolicyDocument
    symbol: str = Field(pattern=r"^[A-Z][A-Z0-9.-]{0,14}$")
    asset_type: AssetType
    sector: str = Field(min_length=1)
    side: OrderSide
    asset_tradable: bool
    regular_session_open: bool
    allowed_symbols: frozenset[str]
    current_weight_pct: Decimal = Field(ge=0)
    proposed_target_weight_pct: Decimal = Field(ge=0)
    current_sector_weight_pct: Decimal = Field(ge=0)
    proposed_sector_weight_pct: Decimal = Field(ge=0)
    cash_pct_after_order: Decimal = Field(ge=0)
    new_exposure_today_pct_after_order: Decimal = Field(ge=0)
    new_positions_today_after_order: int = Field(ge=0)
    weekly_turnover_pct_after_order: Decimal = Field(ge=0)
    trading_days_until_earnings: int | None = None

    @property
    def opens_new_position(self) -> bool:
        return (
            self.side is OrderSide.BUY
            and self.current_weight_pct == 0
            and self.proposed_target_weight_pct > 0
        )

    @property
    def increases_position(self) -> bool:
        return (
            self.side is OrderSide.BUY
            and self.proposed_target_weight_pct > self.current_weight_pct
        )

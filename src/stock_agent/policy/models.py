from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class PolicyModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class HoldingPeriod(PolicyModel):
    minimum: int = Field(gt=0)
    maximum: int = Field(gt=0)

    @model_validator(mode="after")
    def ordered(self) -> "HoldingPeriod":
        if self.minimum > self.maximum:
            raise ValueError("minimum holding period exceeds maximum")
        return self


class Objective(PolicyModel):
    primary: str = Field(min_length=1)
    benchmark: str = Field(min_length=1)
    holding_period_trading_days: HoldingPeriod


class Universe(PolicyModel):
    memberships: tuple[str, ...]
    allowed_etfs: tuple[str, ...]
    minimum_share_price_usd: Decimal = Field(gt=0)
    minimum_market_cap_usd: Decimal = Field(gt=0)
    minimum_average_daily_dollar_volume_usd: Decimal = Field(gt=0)
    prohibited: tuple[str, ...]


class PortfolioPolicy(PolicyModel):
    initial_paper_capital_usd: Decimal = Field(gt=0)
    maximum_initial_position_pct: Decimal = Field(gt=0, le=100)
    maximum_addition_pct: Decimal = Field(gt=0, le=100)
    maximum_single_stock_pct: Decimal = Field(gt=0, le=100)
    maximum_single_etf_pct: Decimal = Field(gt=0, le=100)
    maximum_technology_sector_pct: Decimal = Field(gt=0, le=100)
    maximum_other_sector_pct: Decimal = Field(gt=0, le=100)
    minimum_cash_pct: Decimal = Field(ge=0, le=100)
    maximum_new_exposure_per_day_pct: Decimal = Field(gt=0, le=100)
    maximum_new_positions_per_day: int = Field(gt=0)
    maximum_weekly_turnover_pct: Decimal = Field(gt=0, le=100)
    grandfather_positions_above_limit: bool


class ExecutionPolicy(PolicyModel):
    environment: str
    human_approval_required: bool
    regular_market_hours_only: bool
    allowed_order_types: tuple[str, ...]
    time_in_force: str
    margin_allowed: bool
    short_selling_allowed: bool
    options_allowed: bool
    live_trading_enabled: bool

    @model_validator(mode="after")
    def paper_limit_day_only(self) -> "ExecutionPolicy":
        if (
            self.environment != "PAPER"
            or self.allowed_order_types != ("LIMIT",)
            or self.time_in_force != "DAY"
            or self.margin_allowed
            or self.short_selling_allowed
            or self.options_allowed
            or self.live_trading_enabled
        ):
            raise ValueError("execution policy must remain PAPER, LIMIT, DAY and long-only")
        return self


class FreshnessPolicy(PolicyModel):
    execution_quote_seconds: int = Field(gt=0)
    account_snapshot_seconds: int = Field(gt=0)
    positions_snapshot_seconds: int = Field(gt=0)
    pending_orders_snapshot_seconds: int = Field(gt=0)
    news_search_minutes: int = Field(gt=0)
    recommendation_max_hours: int = Field(gt=0)
    recommendation_expires_at_next_market_close: bool


class AvoidParabolicEntry(PolicyModel):
    enabled: bool
    maximum_pct_above_50_day_average: Decimal = Field(gt=0)


class DecisionPolicy(PolicyModel):
    minimum_executable_confidence: int = Field(ge=0, le=100)
    require_bull_base_bear_cases: bool
    require_contradicting_evidence: bool
    require_invalidation_condition: bool
    unresolved_material_conflict_action: str
    missing_material_data_action: str
    avoid_parabolic_entry: AvoidParabolicEntry
    normal_entry_blackout_before_earnings_trading_days: int = Field(ge=0)


class PausePolicy(PolicyModel):
    daily_loss_pct: Decimal = Field(gt=0)
    weekly_loss_pct: Decimal = Field(gt=0)
    peak_to_trough_drawdown_pct: Decimal = Field(gt=0)
    consecutive_system_rejections: int = Field(gt=0)
    pause_on_reconciliation_failure: bool
    pause_on_required_audit_failure: bool
    cancel_orders_on_pause: bool
    liquidate_positions_on_pause: bool

    @model_validator(mode="after")
    def pause_has_no_side_effects(self) -> "PausePolicy":
        if self.cancel_orders_on_pause or self.liquidate_positions_on_pause:
            raise ValueError("pause must not cancel orders or liquidate positions")
        return self


class Preferences(PolicyModel):
    favor: tuple[str, ...]
    entry_style: tuple[str, ...]
    tax_aware: bool


class PolicyDocument(PolicyModel):
    policy_id: str = Field(min_length=1)
    version: int = Field(gt=0)
    effective_from: date
    objective: Objective
    universe: Universe
    portfolio: PortfolioPolicy
    execution: ExecutionPolicy
    freshness: FreshnessPolicy
    decision: DecisionPolicy
    pause: PausePolicy
    preferences: Preferences

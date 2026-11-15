from collections.abc import Callable
from decimal import Decimal
from uuid import uuid4

from stock_agent.domain.models import RiskCheck, RiskDecision, RiskDecisionValue
from stock_agent.risk.models import AssetType, OrderSide, RiskContext

RiskRule = Callable[[RiskContext], RiskCheck]


def _check(
    context: RiskContext,
    rule_id: str,
    passed: bool,
    observed: object,
    limit: object,
    pass_reason: str,
    failure_reason: str,
) -> RiskCheck:
    return RiskCheck(
        rule_id=rule_id,
        passed=passed,
        observed_value=str(observed),
        limit_value=str(limit),
        reason=pass_reason if passed else failure_reason,
        evidence_timestamp=context.evidence_timestamp,
    )


def _paper_only(context: RiskContext) -> RiskCheck:
    execution = context.policy.execution
    passed = execution.environment == "PAPER" and not execution.live_trading_enabled
    return _check(context, "RSK-ENV-PAPER", passed, execution.environment, "PAPER",
                  "Paper environment is enabled", "Execution is not safely paper-only")


def _allowlist(context: RiskContext) -> RiskCheck:
    passed = context.symbol in context.allowed_symbols
    return _check(context, "RSK-SYMBOL-ALLOWLIST", passed, context.symbol,
                  sorted(context.allowed_symbols), "Symbol is allowlisted",
                  "Symbol is outside the immutable run universe")


def _tradable(context: RiskContext) -> RiskCheck:
    return _check(context, "RSK-ASSET-TRADABLE", context.asset_tradable,
                  context.asset_tradable, True, "Asset is broker-tradable",
                  "Asset is not broker-tradable")


def _regular_session(context: RiskContext) -> RiskCheck:
    required = context.policy.execution.regular_market_hours_only
    passed = not required or context.regular_session_open
    return _check(context, "RSK-REGULAR-SESSION", passed, context.regular_session_open,
                  required, "Regular-session requirement is satisfied",
                  "Order is outside the regular session")


def _long_only(context: RiskContext) -> RiskCheck:
    passed = not (
        context.side is OrderSide.SELL
        and context.proposed_target_weight_pct > context.current_weight_pct
    )
    return _check(context, "RSK-LONG-ONLY", passed, context.proposed_target_weight_pct,
                  ">= 0 and valid sell delta", "Proposal remains long-only",
                  "Proposal would create a short or invalid sell")


def _initial_position(context: RiskContext) -> RiskCheck:
    limit = context.policy.portfolio.maximum_initial_position_pct
    passed = not context.opens_new_position or context.proposed_target_weight_pct <= limit
    return _check(context, "RSK-INITIAL-POSITION", passed,
                  context.proposed_target_weight_pct, limit,
                  "Initial position is within limit", "Initial position exceeds limit")


def _staged_addition(context: RiskContext) -> RiskCheck:
    addition = max(context.proposed_target_weight_pct - context.current_weight_pct, Decimal(0))
    limit = context.policy.portfolio.maximum_addition_pct
    passed = not context.increases_position or context.opens_new_position or addition <= limit
    return _check(context, "RSK-STAGED-ADDITION", passed, addition, limit,
                  "Position addition is within staged limit",
                  "Position addition exceeds staged limit")


def _single_asset(context: RiskContext) -> RiskCheck:
    portfolio = context.policy.portfolio
    limit = (portfolio.maximum_single_etf_pct if context.asset_type is AssetType.ETF
             else portfolio.maximum_single_stock_pct)
    above_before = context.current_weight_pct > limit
    grandfathered = (portfolio.grandfather_positions_above_limit and above_before
                      and context.proposed_target_weight_pct <= context.current_weight_pct)
    passed = context.proposed_target_weight_pct <= limit or grandfathered
    return _check(context, "RSK-SINGLE-ASSET", passed,
                  context.proposed_target_weight_pct, limit,
                  ("Grandfathered over-limit position is not increased" if grandfathered
                   else "Single-asset limit satisfied"),
                  ("Grandfathered over-limit position cannot be increased" if above_before
                   else "Single-asset limit exceeded"))


def _sector(context: RiskContext) -> RiskCheck:
    portfolio = context.policy.portfolio
    limit = (portfolio.maximum_technology_sector_pct if context.sector == "TECHNOLOGY"
             else portfolio.maximum_other_sector_pct)
    grandfathered = (context.current_sector_weight_pct > limit
                      and context.proposed_sector_weight_pct <= context.current_sector_weight_pct)
    passed = context.proposed_sector_weight_pct <= limit or grandfathered
    return _check(context, "RSK-SECTOR-EXPOSURE", passed,
                  context.proposed_sector_weight_pct, limit,
                  "Sector exposure limit satisfied", "Sector exposure limit exceeded")


def _minimum_cash(context: RiskContext) -> RiskCheck:
    limit = context.policy.portfolio.minimum_cash_pct
    passed = context.cash_pct_after_order >= limit
    return _check(context, "RSK-MINIMUM-CASH", passed, context.cash_pct_after_order, limit,
                  "Minimum cash buffer retained", "Minimum cash buffer breached")


def _daily_exposure(context: RiskContext) -> RiskCheck:
    limit = context.policy.portfolio.maximum_new_exposure_per_day_pct
    passed = context.new_exposure_today_pct_after_order <= limit
    return _check(context, "RSK-DAILY-EXPOSURE", passed,
                  context.new_exposure_today_pct_after_order, limit,
                  "Daily new-exposure limit satisfied", "Daily new-exposure limit exceeded")


def _daily_positions(context: RiskContext) -> RiskCheck:
    limit = context.policy.portfolio.maximum_new_positions_per_day
    passed = context.new_positions_today_after_order <= limit
    return _check(context, "RSK-DAILY-NEW-POSITIONS", passed,
                  context.new_positions_today_after_order, limit,
                  "Daily new-position count satisfied", "Daily new-position count exceeded")


def _weekly_turnover(context: RiskContext) -> RiskCheck:
    limit = context.policy.portfolio.maximum_weekly_turnover_pct
    passed = context.weekly_turnover_pct_after_order <= limit
    return _check(context, "RSK-WEEKLY-TURNOVER", passed,
                  context.weekly_turnover_pct_after_order, limit,
                  "Weekly turnover limit satisfied", "Weekly turnover limit exceeded")


def _earnings_blackout(context: RiskContext) -> RiskCheck:
    limit = context.policy.decision.normal_entry_blackout_before_earnings_trading_days
    days = context.trading_days_until_earnings
    blocked = context.opens_new_position and days is not None and 0 <= days <= limit
    return _check(context, "RSK-EARNINGS-BLACKOUT", not blocked, days, limit,
                  "No prohibited near-term earnings event",
                  "Normal new position is inside earnings blackout")


RULES: tuple[RiskRule, ...] = (
    _paper_only, _allowlist, _tradable, _regular_session, _long_only,
    _initial_position, _staged_addition, _single_asset, _sector, _minimum_cash,
    _daily_exposure, _daily_positions, _weekly_turnover, _earnings_blackout,
)


class DeterministicRiskEngine:
    def __init__(self, rules: tuple[RiskRule, ...] = RULES) -> None:
        self._rules = rules

    def evaluate(self, context: RiskContext) -> RiskDecision:
        checks = tuple(rule(context) for rule in self._rules)
        decision = (RiskDecisionValue.APPROVED if all(check.passed for check in checks)
                    else RiskDecisionValue.REJECTED)
        return RiskDecision(
            risk_decision_id=uuid4(), recommendation_id=context.recommendation_id,
            policy_version=str(context.policy.version),
            account_snapshot_id=context.account_snapshot_id,
            evaluated_at=context.evaluated_at, decision=decision, checks=checks,
        )

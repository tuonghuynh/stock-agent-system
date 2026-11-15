from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

import pytest

from stock_agent.domain.models import RiskDecision, RiskDecisionValue
from stock_agent.policy.loader import load_policy
from stock_agent.risk import AssetType, DeterministicRiskEngine, OrderSide, RiskContext

POLICY = load_policy(Path("POLICY_V1.yaml"))


def context(
    side: OrderSide,
    current: str,
    target: str,
    earnings_days: int | None = None,
) -> RiskContext:
    current_weight = Decimal(current)
    target_weight = Decimal(target)
    return RiskContext(
        recommendation_id=uuid4(), account_snapshot_id=uuid4(),
        evaluated_at=datetime(2026, 11, 14, 18, tzinfo=UTC),
        evidence_timestamp=datetime(2026, 11, 14, 17, 59, 50, tzinfo=UTC),
        policy=POLICY, symbol="AAPL", asset_type=AssetType.STOCK,
        sector="TECHNOLOGY", side=side, asset_tradable=True,
        regular_session_open=True, allowed_symbols=frozenset({"AAPL"}),
        current_weight_pct=current_weight, proposed_target_weight_pct=target_weight,
        current_sector_weight_pct=Decimal(20),
        proposed_sector_weight_pct=Decimal(20) + target_weight - current_weight,
        cash_pct_after_order=Decimal(20),
        new_exposure_today_pct_after_order=Decimal(4) if side is OrderSide.BUY else Decimal(0),
        new_positions_today_after_order=1, weekly_turnover_pct_after_order=Decimal(5),
        trading_days_until_earnings=earnings_days,
    )


def check(result: RiskDecision, rule_id: str):  # type: ignore[no-untyped-def]
    return next(item for item in result.checks if item.rule_id == rule_id)


def test_at011_over_limit_position_cannot_be_increased() -> None:
    result = DeterministicRiskEngine().evaluate(context(OrderSide.BUY, "12", "13"))
    assert result.decision is RiskDecisionValue.REJECTED
    assert not check(result, "RSK-SINGLE-ASSET").passed


def test_at012_grandfathered_position_can_be_reduced() -> None:
    result = DeterministicRiskEngine().evaluate(context(OrderSide.SELL, "12", "9"))
    assert result.decision is RiskDecisionValue.APPROVED
    assert check(result, "RSK-SINGLE-ASSET").passed
    assert "Grandfathered" in check(result, "RSK-SINGLE-ASSET").reason


def test_at015_new_position_inside_earnings_blackout_is_rejected() -> None:
    result = DeterministicRiskEngine().evaluate(context(OrderSide.BUY, "0", "3", 2))
    assert result.decision is RiskDecisionValue.REJECTED
    assert not check(result, "RSK-EARNINGS-BLACKOUT").passed


def test_eligible_proposal_returns_all_named_checks() -> None:
    result = DeterministicRiskEngine().evaluate(context(OrderSide.BUY, "4", "6"))
    assert result.decision is RiskDecisionValue.APPROVED
    assert result.policy_version == "1"
    assert len(result.checks) == 14
    assert all(item.rule_id and item.reason and item.limit_value for item in result.checks)


def test_invalid_universe_and_session_fail_without_override() -> None:
    base = context(OrderSide.BUY, "0", "3")
    unsafe = base.model_copy(update={
        "symbol": "TSLA", "allowed_symbols": frozenset({"AAPL"}),
        "asset_tradable": False, "regular_session_open": False,
    })
    result = DeterministicRiskEngine().evaluate(unsafe)
    assert result.decision is RiskDecisionValue.REJECTED
    assert sum(not item.passed for item in result.checks) >= 3


@pytest.mark.parametrize(
    ("field", "value", "rule"),
    [
        ("cash_pct_after_order", Decimal(14), "RSK-MINIMUM-CASH"),
        ("new_exposure_today_pct_after_order", Decimal(11), "RSK-DAILY-EXPOSURE"),
        ("new_positions_today_after_order", 4, "RSK-DAILY-NEW-POSITIONS"),
        ("weekly_turnover_pct_after_order", Decimal(26), "RSK-WEEKLY-TURNOVER"),
    ],
)
def test_portfolio_limits_are_deterministic(field: str, value: object, rule: str) -> None:
    changed = context(OrderSide.BUY, "4", "6").model_copy(update={field: value})
    result = DeterministicRiskEngine().evaluate(changed)
    assert result.decision is RiskDecisionValue.REJECTED
    assert not check(result, rule).passed

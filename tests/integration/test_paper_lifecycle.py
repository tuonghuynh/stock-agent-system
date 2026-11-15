from decimal import Decimal

import pytest
from pydantic import ValidationError

from stock_agent.application import run_fake_paper_demo
from stock_agent.coordinator import RunOutcome
from stock_agent.domain.models import IntentStatus, RecommendationAction, TradeEnvironment
from stock_agent.settings import Settings


def test_at024_at035_eligible_recommendation_fills_without_human_approval() -> None:
    result = run_fake_paper_demo()

    assert result.outcome is RunOutcome.ACCEPTED
    assert result.recommendation_action is RecommendationAction.BUY
    assert result.risk_approved
    assert result.risk_failures == ()
    assert result.intent_id is not None
    assert result.intent_status is IntentStatus.FILLED
    assert result.broker_order_id is not None
    assert result.filled_quantity == Decimal(2)
    assert result.broker_submission_count == 1
    assert not result.human_approval_requested
    assert result.environment is TradeEnvironment.PAPER


def test_rejected_recommendation_has_reasons_and_no_broker_side_effect() -> None:
    result = run_fake_paper_demo(symbol_allowed=False)

    assert result.outcome is RunOutcome.REJECTED
    assert not result.risk_approved
    assert "RSK-SYMBOL-ALLOWLIST" in result.risk_failures
    assert result.intent_id is None
    assert result.intent_status is None
    assert result.broker_order_id is None
    assert result.filled_quantity == 0
    assert result.broker_submission_count == 0


def test_at025_live_configuration_is_rejected_and_not_in_demo_authority() -> None:
    with pytest.raises(ValidationError, match="live trading is not supported"):
        Settings(live_trading_enabled=True)

    result = run_fake_paper_demo()
    assert result.environment is TradeEnvironment.PAPER
    assert not result.human_approval_requested

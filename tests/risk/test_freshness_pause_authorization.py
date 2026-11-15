from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

import pytest

from stock_agent.policy.loader import load_policy
from stock_agent.risk.authorization import RiskAuthorizationService
from stock_agent.risk.engine import DeterministicRiskEngine
from stock_agent.risk.freshness import RiskDataTimestamps, freshness_checks
from stock_agent.risk.models import AssetType, OrderSide, RiskContext
from stock_agent.risk.pause import PauseController, PauseSignals
from stock_agent.risk.reservations import (
    InMemoryReservationStore,
    ReservationCapacity,
    ReservationRequest,
)

POLICY = load_policy(Path("POLICY_V1.yaml"))
NOW = datetime(2026, 11, 14, 20, tzinfo=UTC)


def timestamps(*, quote_age: int = 10) -> RiskDataTimestamps:
    return RiskDataTimestamps(
        quote=NOW - timedelta(seconds=quote_age),
        position=NOW - timedelta(seconds=10),
        pending_orders=NOW - timedelta(seconds=10),
        account=NOW - timedelta(seconds=10),
        buying_power=NOW - timedelta(seconds=10),
    )


def context() -> RiskContext:
    return RiskContext(
        recommendation_id=uuid4(), account_snapshot_id=uuid4(), evaluated_at=NOW,
        evidence_timestamp=NOW - timedelta(seconds=10), policy=POLICY, symbol="AAPL",
        asset_type=AssetType.STOCK, sector="TECHNOLOGY", side=OrderSide.BUY,
        asset_tradable=True, regular_session_open=True,
        allowed_symbols=frozenset({"AAPL"}), current_weight_pct=Decimal(4),
        proposed_target_weight_pct=Decimal(6), current_sector_weight_pct=Decimal(20),
        proposed_sector_weight_pct=Decimal(22), cash_pct_after_order=Decimal(20),
        new_exposure_today_pct_after_order=Decimal(4), new_positions_today_after_order=1,
        weekly_turnover_pct_after_order=Decimal(5),
    )


def reservation() -> ReservationRequest:
    return ReservationRequest(
        reservation_id=uuid4(), intent_id=uuid4(), symbol="AAPL", side=OrderSide.BUY,
        quantity=Decimal(1), cash_required=Decimal(100), created_at=NOW,
    )


def test_at010_missing_or_stale_material_data_cannot_authorize() -> None:
    store = InMemoryReservationStore()
    service = RiskAuthorizationService(
        DeterministicRiskEngine(), store, PauseController(POLICY.pause)
    )
    result = service.authorize(
        context(), timestamps=timestamps(quote_age=61), request=reservation(),
        capacity=ReservationCapacity(settled_cash=Decimal(1000), positions={}),
    )
    assert not result.approved
    assert result.reservation is None
    assert store.active_cash() == 0
    quote_check = next(
        check for check in result.checks if check.rule_id == "RSK-FRESHNESS-QUOTE"
    )
    assert not quote_check.passed


def test_all_five_material_inputs_have_named_freshness_checks() -> None:
    checks = freshness_checks(timestamps(), evaluated_at=NOW, policy=POLICY.freshness)
    assert len(checks) == 5
    assert all(check.passed for check in checks)
    future = replace(timestamps(), buying_power=NOW + timedelta(microseconds=1))
    future_checks = freshness_checks(future, evaluated_at=NOW, policy=POLICY.freshness)
    assert not next(
        check for check in future_checks if check.rule_id == "RSK-FRESHNESS-BUYING-POWER"
    ).passed
    missing = replace(timestamps(), pending_orders=None)
    missing_checks = freshness_checks(missing, evaluated_at=NOW, policy=POLICY.freshness)
    pending_check = next(
        check for check in missing_checks if check.rule_id == "RSK-FRESHNESS-PENDING-ORDERS"
    )
    assert not pending_check.passed
    assert pending_check.observed_value == "MISSING"


@pytest.mark.parametrize(
    ("signals", "reason"),
    [
        (PauseSignals(daily_loss_pct=Decimal(3)), "DAILY_LOSS"),
        (PauseSignals(weekly_loss_pct=Decimal(6)), "WEEKLY_LOSS"),
        (PauseSignals(drawdown_pct=Decimal(10)), "DRAWDOWN"),
        (PauseSignals(consecutive_system_rejections=3), "SYSTEM_REJECTIONS"),
        (PauseSignals(reconciliation_failed=True), "RECONCILIATION_FAILURE"),
    ],
)
def test_rel005_thresholds_latch_pause(signals: PauseSignals, reason: str) -> None:
    controller = PauseController(POLICY.pause)
    state = controller.observe(signals)
    assert state.paused
    assert reason in state.reasons
    assert controller.observe(PauseSignals()).paused
    with pytest.raises(PermissionError, match="paused"):
        controller.require_submissions_enabled()


def test_at023_pause_blocks_new_orders_but_does_not_cancel_or_liquidate() -> None:
    controller = PauseController(POLICY.pause)
    state = controller.observe(PauseSignals(reconciliation_failed=True))
    assert state.paused
    assert state.monitoring_enabled and state.reconciliation_enabled
    assert not state.cancel_orders_requested
    assert not state.liquidation_requested

    service = RiskAuthorizationService(
        DeterministicRiskEngine(), InMemoryReservationStore(), controller
    )
    with pytest.raises(PermissionError, match="paused"):
        service.authorize(
            context(), timestamps=timestamps(), request=reservation(),
            capacity=ReservationCapacity(settled_cash=Decimal(1000), positions={}),
        )

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from stock_agent.evidence import PriceBar, TechnicalIndicatorCalculator

START = datetime(2026, 1, 1, 21, tzinfo=UTC)


def bar(day: int, close: int) -> PriceBar:
    return PriceBar(timestamp=START + timedelta(days=day), close=Decimal(close))


def test_dat003_sma_ema_and_wilder_rsi_are_deterministic() -> None:
    calculator = TechnicalIndicatorCalculator()
    bars = tuple(bar(day, day) for day in range(1, 7))

    first = calculator.calculate(
        bars, as_of=START + timedelta(days=6), trend_period=3, momentum_period=3
    )
    second = calculator.calculate(
        tuple(reversed(bars)),
        as_of=START + timedelta(days=6),
        trend_period=3,
        momentum_period=3,
    )

    assert first == second
    assert first.simple_moving_average == Decimal("5.00000000")
    assert first.exponential_moving_average == Decimal("5.00000000")
    assert first.relative_strength_index == Decimal("100.00000000")


def test_insufficient_history_is_explicit_and_flat_rsi_is_neutral() -> None:
    calculator = TechnicalIndicatorCalculator()
    bars = tuple(bar(day, 10) for day in range(1, 5))

    assert calculator.sma(bars, 5) is None
    assert calculator.ema(bars, 5) is None
    assert calculator.wilder_rsi(bars, 3) == Decimal("50.00000000")


def test_at029_rejects_future_price_bars() -> None:
    with pytest.raises(ValueError, match="newer than as_of"):
        TechnicalIndicatorCalculator().calculate(
            (bar(1, 10), bar(3, 11)),
            as_of=START + timedelta(days=2),
            trend_period=2,
            momentum_period=2,
        )


def test_duplicate_timestamps_are_rejected() -> None:
    with pytest.raises(ValueError, match="duplicate"):
        TechnicalIndicatorCalculator().calculate(
            (bar(1, 10), bar(1, 11)),
            as_of=START + timedelta(days=2),
            trend_period=2,
            momentum_period=2,
        )

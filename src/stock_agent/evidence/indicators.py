from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, localcontext

_OUTPUT_QUANTUM = Decimal("0.00000001")


@dataclass(frozen=True, slots=True)
class PriceBar:
    timestamp: datetime
    close: Decimal

    def __post_init__(self) -> None:
        if self.timestamp.tzinfo is None or self.timestamp.utcoffset() is None:
            raise ValueError("timestamp must be timezone-aware")
        if self.close <= 0:
            raise ValueError("close must be positive")


@dataclass(frozen=True, slots=True)
class TechnicalIndicators:
    as_of: datetime
    latest_bar_at: datetime
    simple_moving_average: Decimal | None
    exponential_moving_average: Decimal | None
    relative_strength_index: Decimal | None


class TechnicalIndicatorCalculator:
    """Pure Decimal calculations with deterministic point-in-time ordering."""

    def calculate(
        self,
        bars: tuple[PriceBar, ...],
        *,
        as_of: datetime,
        trend_period: int,
        momentum_period: int,
    ) -> TechnicalIndicators:
        history = self._history(bars, as_of)
        return TechnicalIndicators(
            as_of=as_of,
            latest_bar_at=history[-1].timestamp,
            simple_moving_average=self.sma(history, trend_period),
            exponential_moving_average=self.ema(history, trend_period),
            relative_strength_index=self.wilder_rsi(history, momentum_period),
        )

    @staticmethod
    def sma(bars: tuple[PriceBar, ...], period: int) -> Decimal | None:
        _require_period(period)
        if len(bars) < period:
            return None
        with localcontext() as context:
            context.prec = 34
            value = sum((bar.close for bar in bars[-period:]), start=Decimal(0)) / period
        return _output(value)

    @staticmethod
    def ema(bars: tuple[PriceBar, ...], period: int) -> Decimal | None:
        _require_period(period)
        if len(bars) < period:
            return None
        with localcontext() as context:
            context.prec = 34
            value = sum((bar.close for bar in bars[:period]), start=Decimal(0)) / period
            alpha = Decimal(2) / Decimal(period + 1)
            for bar in bars[period:]:
                value = (bar.close - value) * alpha + value
        return _output(value)

    @staticmethod
    def wilder_rsi(bars: tuple[PriceBar, ...], period: int) -> Decimal | None:
        _require_period(period)
        if len(bars) <= period:
            return None
        with localcontext() as context:
            context.prec = 34
            deltas = [bars[index].close - bars[index - 1].close for index in range(1, len(bars))]
            gains = [max(delta, Decimal(0)) for delta in deltas]
            losses = [max(-delta, Decimal(0)) for delta in deltas]
            average_gain = sum(gains[:period], start=Decimal(0)) / period
            average_loss = sum(losses[:period], start=Decimal(0)) / period
            for gain, loss in zip(gains[period:], losses[period:], strict=True):
                average_gain = (average_gain * (period - 1) + gain) / period
                average_loss = (average_loss * (period - 1) + loss) / period
            if average_gain == 0 and average_loss == 0:
                return _output(Decimal(50))
            if average_loss == 0:
                return _output(Decimal(100))
            relative_strength = average_gain / average_loss
            value = Decimal(100) - Decimal(100) / (Decimal(1) + relative_strength)
        return _output(value)

    @staticmethod
    def _history(bars: tuple[PriceBar, ...], as_of: datetime) -> tuple[PriceBar, ...]:
        if as_of.tzinfo is None or as_of.utcoffset() is None:
            raise ValueError("as_of must be timezone-aware")
        if not bars:
            raise ValueError("bars must not be empty")
        history = tuple(sorted(bars, key=lambda bar: bar.timestamp))
        timestamps = {bar.timestamp for bar in history}
        if len(timestamps) != len(history):
            raise ValueError("duplicate price-bar timestamp")
        if history[-1].timestamp > as_of:
            raise ValueError("price bar is newer than as_of")
        return history


def _require_period(period: int) -> None:
    if period < 1:
        raise ValueError("period must be positive")


def _output(value: Decimal) -> Decimal:
    return value.quantize(_OUTPUT_QUANTUM)

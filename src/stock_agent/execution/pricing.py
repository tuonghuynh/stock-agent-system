"""Deterministic side-aware limit-price construction."""

from decimal import ROUND_CEILING, ROUND_FLOOR, Decimal

from stock_agent.domain.models import TradeSide


def construct_limit_price(
    *, side: TradeSide, reference_price: Decimal, offset_bps: int, tick_size: Decimal
) -> Decimal:
    if reference_price <= 0 or tick_size <= 0 or offset_bps < 0:
        raise ValueError("price, tick size and offset must be valid")
    multiplier = Decimal(1) + (
        Decimal(offset_bps) / Decimal(10_000)
        if side is TradeSide.BUY
        else -Decimal(offset_bps) / Decimal(10_000)
    )
    raw_ticks = reference_price * multiplier / tick_size
    rounding = ROUND_FLOOR if side is TradeSide.BUY else ROUND_CEILING
    return raw_ticks.to_integral_value(rounding=rounding) * tick_size

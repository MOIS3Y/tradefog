"""Pure True Range and Wilder ATR calculations."""

from collections.abc import Sequence
from decimal import ROUND_HALF_EVEN, Decimal, localcontext
from itertools import pairwise
from typing import Protocol

from tradefog.journal.market_data.types import AtrTargetComparison

ATR_PERIOD = 14
ATR_REFERENCE_PERCENT = Decimal(75)
PERCENT_QUANTUM = Decimal("0.0001")


class CandlePrices(Protocol):
    """Structural price input accepted by volatility calculations."""

    @property
    def high_price(self) -> Decimal:
        """Return the session high."""
        ...

    @property
    def low_price(self) -> Decimal:
        """Return the session low."""
        ...

    @property
    def close_price(self) -> Decimal:
        """Return the session close."""
        ...


def calculate_true_range(
    candle: CandlePrices,
    previous_close: Decimal,
) -> Decimal:
    """Return the greatest intraday or previous-close displacement."""
    return max(
        candle.high_price - candle.low_price,
        abs(candle.high_price - previous_close),
        abs(candle.low_price - previous_close),
    )


def calculate_wilder_atr(
    candles: Sequence[CandlePrices],
    *,
    period: int = ATR_PERIOD,
) -> Decimal | None:
    """Return standard Wilder ATR seeded by the first period TR values.

    A period of 14 needs at least 15 ordered closed candles because the
    first True Range uses the preceding candle's close.
    """
    if period <= 0:
        raise ValueError("ATR period must be positive.")
    if len(candles) < period + 1:
        return None
    true_ranges = [
        calculate_true_range(candle, previous.close_price)
        for previous, candle in pairwise(candles)
    ]
    with localcontext() as context:
        context.prec = 96
        atr = sum(true_ranges[:period], start=Decimal(0)) / period
        for true_range in true_ranges[period:]:
            atr = (atr * (period - 1) + true_range) / period
        return +atr


def compare_target_move_with_atr(
    target_movement: Decimal,
    atr_value: Decimal | None,
) -> AtrTargetComparison | None:
    """Compare an exact planned price move with the 75% ATR reference."""
    if atr_value is None or atr_value <= 0:
        return None
    if target_movement < 0:
        raise ValueError("Target movement cannot be negative.")
    with localcontext() as context:
        context.prec = 96
        percent = (target_movement / atr_value * Decimal(100)).quantize(
            PERCENT_QUANTUM,
            rounding=ROUND_HALF_EVEN,
        )
        fits_reference = (
            target_movement
            <= atr_value * ATR_REFERENCE_PERCENT / Decimal(100)
        )
    return AtrTargetComparison(
        movement=target_movement,
        percent_of_atr=percent,
        fits_seventy_five_percent=fits_reference,
    )

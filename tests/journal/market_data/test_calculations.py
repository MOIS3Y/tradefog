"""Tests for deterministic True Range and Wilder ATR."""

from datetime import date, timedelta
from decimal import Decimal

from pytest import raises

from tradefog.journal.market_data.calculations import (
    calculate_true_range,
    calculate_wilder_atr,
    compare_target_move_with_atr,
)
from tradefog.journal.market_data.types import CandleValue


def candle(day: int, close: str, high: str, low: str) -> CandleValue:
    """Build one exact calculation value."""
    return CandleValue(
        trading_date=date(2026, 1, 1) + timedelta(days=day),
        open_price=Decimal(close),
        high_price=Decimal(high),
        low_price=Decimal(low),
        close_price=Decimal(close),
        source="MANUAL",
    )


def test_true_range_includes_gap_from_previous_close() -> None:
    """An overnight displacement can exceed the intraday range."""
    value = calculate_true_range(
        candle(1, "108", "110", "107"),
        previous_close=Decimal(100),
    )

    assert value == Decimal(10)


def test_wilder_atr_requires_previous_close_plus_fourteen_ranges() -> None:
    """ATR(14) starts only after fifteen ordered closed candles."""
    candles = [candle(day, "100", "102", "98") for day in range(14)]

    assert calculate_wilder_atr(candles) is None

    candles.append(candle(14, "100", "102", "98"))
    assert calculate_wilder_atr(candles) == Decimal(4)


def test_wilder_smoothing_uses_previous_atr() -> None:
    """Later True Range values use Wilder's recursive smoothing."""
    candles = [candle(day, "100", "102", "98") for day in range(15)]
    candles.append(candle(15, "100", "107", "93"))

    atr = calculate_wilder_atr(candles)
    assert atr is not None
    assert atr.quantize(Decimal("0.0001")) == Decimal("4.7143")


def test_atr_period_must_be_positive() -> None:
    """Invalid periods fail explicitly rather than divide by zero."""
    with raises(ValueError):
        _ = calculate_wilder_atr([], period=0)


def test_target_move_is_compared_with_seventy_five_percent_atr() -> None:
    """The advisory threshold compares exact price movement, not P&L."""
    inside = compare_target_move_with_atr(Decimal(75), Decimal(100))
    outside = compare_target_move_with_atr(
        Decimal("75.000001"),
        Decimal(100),
    )

    assert inside is not None
    assert inside.percent_of_atr == Decimal(75)
    assert inside.fits_seventy_five_percent is True
    assert outside is not None
    assert outside.percent_of_atr == Decimal("75.0000")
    assert outside.fits_seventy_five_percent is False


def test_target_move_comparison_requires_positive_atr() -> None:
    """Missing or flat volatility leaves the advisory comparison absent."""
    assert compare_target_move_with_atr(Decimal(10), None) is None
    assert compare_target_move_with_atr(Decimal(10), Decimal(0)) is None

    with raises(ValueError):
        _ = compare_target_move_with_atr(Decimal(-1), Decimal(100))

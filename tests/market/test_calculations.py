"""Unit tests for True Range, Wilder ATR(14), and market context."""

import datetime
from decimal import Decimal

import pytest

from tradefog.market.calculations import (
    calculate_atr_14,
    calculate_market_context,
    true_range,
)
from tradefog.market.types import DailyCandle


def _make_sample_candles(count: int = 15) -> list[DailyCandle]:
    """Generate a predictable sequence of daily candles for testing."""
    base_date = datetime.date(2026, 8, 1)
    candles: list[DailyCandle] = []
    for index in range(count):
        day = base_date + datetime.timedelta(days=index)
        # Low=100, High=110, Close=105, Open=102 -> Constant TR of 10
        candles.append(
            DailyCandle(
                date=day,
                open=Decimal("102.00"),
                high=Decimal("110.00"),
                low=Decimal("100.00"),
                close=Decimal("105.00"),
            )
        )
    return candles


def test_true_range_without_previous_close() -> None:
    tr = true_range(Decimal("110.00"), Decimal("100.00"), None)
    assert tr == Decimal("10.00")


def test_true_range_with_gap_up() -> None:
    # Previous close 100, current candle 105 to 115
    # High - Low = 10, High - PrevClose = 15, Low - PrevClose = 5 -> TR = 15
    tr = true_range(Decimal("115.00"), Decimal("105.00"), Decimal("100.00"))
    assert tr == Decimal("15.00")


def test_true_range_with_gap_down() -> None:
    # Previous close 120, current candle 100 to 110
    # High - Low = 10, High - PrevClose = 10, Low - PrevClose = 20 -> TR = 20
    tr = true_range(Decimal("110.00"), Decimal("100.00"), Decimal("120.00"))
    assert tr == Decimal("20.00")


def test_calculate_atr_14_requires_minimum_candles() -> None:
    short_candles = _make_sample_candles(13)
    with pytest.raises(ValueError, match="At least 14"):
        calculate_atr_14(short_candles)


def test_calculate_atr_14_constant_volatility() -> None:
    candles = _make_sample_candles(20)
    atr = calculate_atr_14(candles)
    assert atr == Decimal("10.00")


def test_calculate_market_context() -> None:
    candles = _make_sample_candles(16)
    session_candle = DailyCandle(
        date=datetime.date(2026, 8, 17),
        open=Decimal("105.00"),
        high=Decimal("115.00"),
        low=Decimal("108.00"),
        close=Decimal("112.00"),
    )
    context = calculate_market_context(
        closed_candles=candles,
        session_candle=session_candle,
        source="auto",
    )

    assert context.atr_value == Decimal("10.00")
    assert context.contributing_date == candles[-1].date
    assert len(context.candles) == 14
    assert context.observed_session_range == Decimal("7.00")
    assert context.session_range_percent == Decimal("70.00")
    assert context.source == "auto"
    assert not context.is_stale

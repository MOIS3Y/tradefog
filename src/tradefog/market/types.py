"""Typed data structures for market candles and volatility context."""

import datetime
from dataclasses import dataclass
from decimal import Decimal
from typing import final


@final
class MarketDataError(Exception):
    """Raised when on-demand market data cannot be fetched or parsed."""


@dataclass(frozen=True, slots=True)
class DailyCandle:
    """One closed or in-progress daily OHLC candle."""

    date: datetime.date
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal


@dataclass(frozen=True, slots=True)
class ATRContext:
    """Calculated ATR(14) context and recent price action for a trade."""

    atr_value: Decimal
    contributing_date: datetime.date
    candles: list[DailyCandle]
    observed_session_range: Decimal | None = None
    session_range_percent: Decimal | None = None
    source: str = "auto"
    is_stale: bool = False

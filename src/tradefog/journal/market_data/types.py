"""Typed values shared across market-data boundaries."""

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal


def _exact_decimal_string(value: Decimal) -> str:
    """Remove stored scale padding without rounding the decimal value."""
    rendered = format(value, "f")
    if "." not in rendered:
        return rendered
    return rendered.rstrip("0").rstrip(".")


@dataclass(frozen=True, slots=True)
class CandleValue:
    """Price facts required for daily range calculations."""

    trading_date: date
    open_price: Decimal
    high_price: Decimal
    low_price: Decimal
    close_price: Decimal
    source: str


@dataclass(frozen=True, slots=True)
class ProviderDailyData:
    """Closed candles plus an optional still-forming daily session."""

    closed_candles: tuple[CandleValue, ...]
    current_session: CandleValue | None
    observed_at: datetime


@dataclass(frozen=True, slots=True)
class AtrTargetComparison:
    """Compare the planned entry-to-target move with daily volatility."""

    movement: Decimal
    percent_of_atr: Decimal
    fits_seventy_five_percent: bool

    @property
    def tape_percent(self) -> Decimal:
        """Cap the planned movement at the end of the visual ATR tape."""
        return min(self.percent_of_atr, Decimal(100))


@dataclass(frozen=True, slots=True)
class MarketContext:
    """Date-aware ATR and separately observed current-session range."""

    context_date: date
    chart_candles: tuple[CandleValue, ...]
    atr_value: Decimal | None
    atr_as_of_date: date | None
    atr_source: str
    seventy_five_percent_atr: Decimal | None
    session_range: Decimal | None
    session_range_percent: Decimal | None
    session_observed_at: datetime | None
    refreshed_at: datetime | None
    is_stale: bool
    provider_error: str

    @property
    def candle_chart_data(self) -> list[dict[str, str]]:
        """Return exact strings for the browser's two-week candle chart."""
        return [
            {
                "date": candle.trading_date.isoformat(),
                "open": _exact_decimal_string(candle.open_price),
                "high": _exact_decimal_string(candle.high_price),
                "low": _exact_decimal_string(candle.low_price),
                "close": _exact_decimal_string(candle.close_price),
            }
            for candle in self.chart_candles
        ]

    @property
    def range_tape_percent(self) -> Decimal:
        """Cap the observed range at the end of the visual ATR tape."""
        if self.session_range_percent is None:
            return Decimal(0)
        return min(self.session_range_percent, Decimal(100))

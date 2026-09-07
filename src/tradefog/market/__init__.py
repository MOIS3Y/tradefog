"""Market data and volatility calculations package."""

from tradefog.market.calculations import (
    calculate_atr_14,
    calculate_market_context,
    true_range,
)
from tradefog.market.providers.binance import fetch_binance_daily_candles
from tradefog.market.providers.bybit import fetch_bybit_daily_candles
from tradefog.market.providers.yfinance import fetch_yfinance_daily_candles
from tradefog.market.service import (
    fetch_atr_context,
    fetch_bybit_atr_context,
    fetch_daily_candles,
)
from tradefog.market.types import (
    ATRContext,
    DailyCandle,
    MarketDataError,
)

__all__ = [
    "ATRContext",
    "DailyCandle",
    "MarketDataError",
    "calculate_atr_14",
    "calculate_market_context",
    "fetch_atr_context",
    "fetch_binance_daily_candles",
    "fetch_bybit_atr_context",
    "fetch_bybit_daily_candles",
    "fetch_daily_candles",
    "fetch_yfinance_daily_candles",
    "true_range",
]

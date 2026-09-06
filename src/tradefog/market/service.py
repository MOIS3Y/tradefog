"""High-level market data service for trade context and volatility."""

import datetime

import httpx

from tradefog.market.calculations import calculate_market_context
from tradefog.market.providers.bybit import fetch_bybit_daily_candles
from tradefog.market.types import ATRContext, MarketDataError


def _resolve_bybit_category(product_kind: str) -> str:
    """Map the domain product kind to the Bybit V5 market category."""
    kind = product_kind.lower()
    if kind in ("perpetual_future", "linear"):
        return "linear"
    return "spot"


def fetch_bybit_atr_context(
    symbol: str,
    *,
    product_kind: str = "spot",
    trade_date: datetime.date | None = None,
    client: httpx.Client | None = None,
) -> ATRContext:
    """Fetch closed daily candles from Bybit and calculate the ATR context.

    Filters closed candles strictly prior to ``trade_date`` (or today if not
    specified). If a candle exists for ``trade_date``, its observed range is
    included as the current session range.
    """
    if trade_date is None:
        trade_date = datetime.datetime.now(datetime.UTC).date()

    category = _resolve_bybit_category(product_kind)
    candles = fetch_bybit_daily_candles(
        symbol=symbol, category=category, limit=40, client=client
    )

    closed_candles = [candle for candle in candles if candle.date < trade_date]
    session_candles = [
        candle for candle in candles if candle.date == trade_date
    ]
    session_candle = session_candles[0] if session_candles else None

    if len(closed_candles) < 14:
        raise MarketDataError(
            f"Insufficient closed daily candles ({len(closed_candles)}/14) "
            + f"before {trade_date} for {symbol}."
        )

    return calculate_market_context(
        closed_candles=closed_candles,
        session_candle=session_candle,
        source="auto",
    )

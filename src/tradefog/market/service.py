"""High-level market data service for trade context and volatility."""

import datetime

import httpx

from tradefog.market.calculations import calculate_market_context
from tradefog.market.providers.binance import fetch_binance_daily_candles
from tradefog.market.providers.bybit import fetch_bybit_daily_candles
from tradefog.market.providers.yfinance import fetch_yfinance_daily_candles
from tradefog.market.types import ATRContext, DailyCandle, MarketDataError


def _resolve_bybit_category(product_kind: str) -> str:
    """Map domain product kind to Bybit V5 market category."""
    kind = product_kind.lower()
    if kind in ("perpetual_future", "linear"):
        return "linear"
    return "spot"


def fetch_daily_candles(
    provider: str,
    symbol: str,
    *,
    product_kind: str = "spot",
    limit: int = 40,
    client: httpx.Client | None = None,
) -> list[DailyCandle]:
    """Fetch daily candles from the configured market data provider."""
    normalized_provider = provider.lower().strip()

    if normalized_provider == "bybit":
        category = _resolve_bybit_category(product_kind)
        return fetch_bybit_daily_candles(
            symbol=symbol, category=category, limit=limit, client=client
        )

    if normalized_provider == "binance":
        category = (
            "perpetual_future"
            if product_kind == "perpetual_future"
            else "spot"
        )
        return fetch_binance_daily_candles(
            symbol=symbol, category=category, limit=limit, client=client
        )

    if normalized_provider in ("yfinance", "yahoo_finance", "yahoo"):
        return fetch_yfinance_daily_candles(symbol=symbol, client=client)

    raise MarketDataError(
        f"Unsupported or manual-only market data provider: {provider}"
    )


def fetch_atr_context(
    provider: str,
    symbol: str,
    *,
    product_kind: str = "spot",
    trade_date: datetime.date | None = None,
    client: httpx.Client | None = None,
) -> ATRContext:
    """Fetch closed daily candles from provider and calculate ATR context.

    Filters closed candles strictly prior to ``trade_date`` (or today if not
    specified). If a candle exists for ``trade_date``, its observed range is
    included as the current session range.
    """
    if trade_date is None:
        trade_date = datetime.datetime.now(datetime.UTC).date()

    candles = fetch_daily_candles(
        provider=provider,
        symbol=symbol,
        product_kind=product_kind,
        limit=40,
        client=client,
    )

    closed_candles = [candle for candle in candles if candle.date < trade_date]
    session_candle = next(
        (candle for candle in candles if candle.date == trade_date), None,
    )

    if len(closed_candles) < 14:
        raise MarketDataError(
            f"Insufficient closed daily candles ({len(closed_candles)}/14) "
            + f"before {trade_date} for {symbol} ({provider})."
        )

    return calculate_market_context(
        closed_candles=closed_candles,
        session_candle=session_candle,
        source="auto",
    )


def fetch_bybit_atr_context(
    symbol: str,
    *,
    product_kind: str = "spot",
    trade_date: datetime.date | None = None,
    client: httpx.Client | None = None,
) -> ATRContext:
    """Convenience alias for Bybit ATR context fetching."""
    return fetch_atr_context(
        provider="bybit",
        symbol=symbol,
        product_kind=product_kind,
        trade_date=trade_date,
        client=client,
    )

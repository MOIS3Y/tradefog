"""Binance public Kline API provider for daily market candles."""

import datetime
from decimal import Decimal, InvalidOperation
from typing import cast

import httpx

from tradefog.market.types import DailyCandle, MarketDataError

BINANCE_SPOT_KLINE_URL = "https://api.binance.com/api/v3/klines"
BINANCE_FUTURES_KLINE_URL = "https://fapi.binance.com/fapi/v1/klines"
DEFAULT_TIMEOUT = 10.0


def fetch_binance_daily_candles(
    symbol: str,
    *,
    category: str = "spot",
    limit: int = 35,
    client: httpx.Client | None = None,
) -> list[DailyCandle]:
    """Fetch daily candles from Binance public Kline API.

    Supports both spot and perpetual futures (linear) markets.
    Returns a list of :class:`DailyCandle` sorted chronologically in
    ascending order.
    """
    normalized_category = category.lower()
    is_futures = normalized_category in (
        "perpetual_future",
        "linear",
        "futures",
    )

    endpoint_url = (
        BINANCE_FUTURES_KLINE_URL if is_futures else BINANCE_SPOT_KLINE_URL
    )

    clean_symbol = (
        symbol.upper()
        .replace("/", "")
        .replace("-", "")
        .replace("_", "")
        .replace(" ", "")
        .strip()
    )

    params: dict[str, str | int] = {
        "symbol": clean_symbol,
        "interval": "1d",
        "limit": min(limit, 200),
    }

    try:
        if client is not None:
            response = client.get(
                endpoint_url, params=params, timeout=DEFAULT_TIMEOUT
            )
        else:
            with httpx.Client(timeout=DEFAULT_TIMEOUT) as http_client:
                response = http_client.get(endpoint_url, params=params)
    except httpx.TimeoutException as error:
        raise MarketDataError(
            f"Binance request timed out for {symbol}."
        ) from error
    except httpx.RequestError as error:
        raise MarketDataError(
            f"Failed to connect to Binance for {symbol}: {error}"
        ) from error

    if response.status_code != 200:
        raise MarketDataError(
            f"Binance API returned HTTP {response.status_code} for {symbol}."
        )

    try:
        raw_payload: object = cast(object, response.json())
    except Exception as error:
        raise MarketDataError(
            f"Invalid JSON received from Binance for {symbol}."
        ) from error

    if not isinstance(raw_payload, list):
        raise MarketDataError(
            f"Unexpected response format from Binance for {symbol}."
        )

    candle_items = cast(list[list[object]], raw_payload)
    if not candle_items:
        raise MarketDataError(
            f"No candle data returned by Binance for {symbol}."
        )

    candles: list[DailyCandle] = []
    for item in candle_items:
        if len(item) < 5:
            continue
        try:
            timestamp_ms = int(str(item[0]))
            candle_date = datetime.datetime.fromtimestamp(
                timestamp_ms / 1000, tz=datetime.UTC
            ).date()
            candle = DailyCandle(
                date=candle_date,
                open=Decimal(str(item[1])),
                high=Decimal(str(item[2])),
                low=Decimal(str(item[3])),
                close=Decimal(str(item[4])),
            )
            candles.append(candle)
        except (ValueError, InvalidOperation) as error:
            raise MarketDataError(
                f"Malformed candle record from Binance for {symbol}: {item}"
            ) from error

    candles.sort(key=lambda c: c.date)
    return candles

"""Yahoo Finance chart API provider for daily market candles."""

import datetime
from decimal import Decimal, InvalidOperation
from typing import cast

import httpx

from tradefog.market.types import DailyCandle, MarketDataError

YFINANCE_CHART_URL = (
    "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
)
DEFAULT_TIMEOUT = 10.0
DEFAULT_USER_AGENT = "Mozilla/5.0 (Tradefog Journal)"


def fetch_yfinance_daily_candles(
    symbol: str,
    *,
    client: httpx.Client | None = None,
) -> list[DailyCandle]:
    """Fetch daily candles from Yahoo Finance chart API.

    Returns a list of :class:`DailyCandle` sorted chronologically in
    ascending order.
    """
    clean_symbol = symbol.strip().upper()
    url = YFINANCE_CHART_URL.format(symbol=clean_symbol)
    params = {
        "interval": "1d",
        "range": "3mo",
    }
    headers = {
        "User-Agent": DEFAULT_USER_AGENT,
    }

    try:
        if client is not None:
            response = client.get(
                url, params=params, headers=headers, timeout=DEFAULT_TIMEOUT
            )
        else:
            with httpx.Client(timeout=DEFAULT_TIMEOUT) as http_client:
                response = http_client.get(url, params=params, headers=headers)
    except httpx.TimeoutException as error:
        raise MarketDataError(
            f"Yahoo Finance request timed out for {symbol}."
        ) from error
    except httpx.RequestError as error:
        raise MarketDataError(
            f"Failed to connect to Yahoo Finance for {symbol}: {error}"
        ) from error

    if response.status_code != 200:
        raise MarketDataError(
            f"Yahoo Finance API returned HTTP {response.status_code} for {symbol}."
        )

    try:
        raw_payload: object = cast(object, response.json())
    except Exception as error:
        raise MarketDataError(
            f"Invalid JSON received from Yahoo Finance for {symbol}."
        ) from error

    if not isinstance(raw_payload, dict):
        raise MarketDataError(
            f"Unexpected response format from Yahoo Finance for {symbol}."
        )

    payload = cast(dict[str, object], raw_payload)
    chart_obj = payload.get("chart")
    if not isinstance(chart_obj, dict):
        raise MarketDataError(
            f"No chart object in Yahoo Finance response for {symbol}."
        )

    chart_dict = cast(dict[str, object], chart_obj)
    error_obj = chart_dict.get("error")
    if error_obj is not None:
        raise MarketDataError(f"Yahoo Finance error for {symbol}: {error_obj}")

    results = chart_dict.get("result")
    if not isinstance(results, list) or not results:
        raise MarketDataError(
            f"No chart result returned by Yahoo Finance for {symbol}."
        )

    first_result = cast(dict[str, object], results[0])
    timestamps = cast(list[int], first_result.get("timestamp") or [])
    indicators = cast(dict[str, object], first_result.get("indicators") or {})
    quotes = cast(list[dict[str, list[object]]], indicators.get("quote") or [])

    if not timestamps or not quotes:
        raise MarketDataError(
            f"No candle timestamps returned by Yahoo Finance for {symbol}."
        )

    quote_data = quotes[0]
    opens = quote_data.get("open") or []
    highs = quote_data.get("high") or []
    lows = quote_data.get("low") or []
    closes = quote_data.get("close") or []

    candles: list[DailyCandle] = []
    for i, ts in enumerate(timestamps):
        if (
            i >= len(opens)
            or i >= len(highs)
            or i >= len(lows)
            or i >= len(closes)
        ):
            break

        raw_o = opens[i]
        raw_h = highs[i]
        raw_l = lows[i]
        raw_c = closes[i]

        if raw_o is None or raw_h is None or raw_l is None or raw_c is None:
            continue

        try:
            candle_date = datetime.datetime.fromtimestamp(
                int(ts), tz=datetime.UTC
            ).date()
            candle = DailyCandle(
                date=candle_date,
                open=Decimal(str(raw_o)),
                high=Decimal(str(raw_h)),
                low=Decimal(str(raw_l)),
                close=Decimal(str(raw_c)),
            )
            candles.append(candle)
        except (ValueError, InvalidOperation) as error:
            raise MarketDataError(
                f"Malformed candle record from Yahoo Finance for {symbol} at index {i}."
            ) from error

    candles.sort(key=lambda c: c.date)
    return candles

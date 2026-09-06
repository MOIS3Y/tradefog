"""Bybit public Kline API provider for daily market candles."""

import datetime
from decimal import Decimal, InvalidOperation
from typing import cast

import httpx

from tradefog.market.types import DailyCandle, MarketDataError

BYBIT_KLINE_URL = "https://api.bybit.com/v5/market/kline"
DEFAULT_TIMEOUT = 10.0


def fetch_bybit_daily_candles(
    symbol: str,
    *,
    category: str = "spot",
    limit: int = 35,
    client: httpx.Client | None = None,
) -> list[DailyCandle]:
    """Fetch daily candles from Bybit public V5 Kline API.

    Returns a list of :class:`DailyCandle` sorted chronologically in
    ascending order.
    """
    normalized_category = category.lower()
    if normalized_category not in ("spot", "linear", "inverse"):
        normalized_category = "spot"

    params: dict[str, str | int] = {
        "category": normalized_category,
        "symbol": symbol.upper(),
        "interval": "D",
        "limit": min(limit, 200),
    }

    try:
        if client is not None:
            response = client.get(
                BYBIT_KLINE_URL, params=params, timeout=DEFAULT_TIMEOUT
            )
        else:
            with httpx.Client(timeout=DEFAULT_TIMEOUT) as http_client:
                response = http_client.get(BYBIT_KLINE_URL, params=params)
    except httpx.TimeoutException as error:
        raise MarketDataError(
            f"Bybit request timed out for {symbol}."
        ) from error
    except httpx.RequestError as error:
        raise MarketDataError(
            f"Failed to connect to Bybit for {symbol}: {error}"
        ) from error

    if response.status_code != 200:
        raise MarketDataError(
            f"Bybit API returned HTTP {response.status_code} for {symbol}."
        )

    try:
        raw_payload: object = response.json()
    except Exception as error:
        raise MarketDataError(
            f"Invalid JSON received from Bybit for {symbol}."
        ) from error

    if not isinstance(raw_payload, dict):
        raise MarketDataError(
            f"Unexpected response format from Bybit for {symbol}."
        )

    payload = cast(dict[str, object], raw_payload)
    ret_code = payload.get("retCode")
    if ret_code != 0:
        ret_msg = str(payload.get("retMsg", "Unknown error"))
        raise MarketDataError(
            f"Bybit API error {ret_code} for {symbol}: {ret_msg}"
        )

    result_obj = payload.get("result")
    raw_list = (
        cast(dict[str, object], result_obj).get("list")
        if isinstance(result_obj, dict)
        else None
    )
    if not isinstance(raw_list, list) or not raw_list:
        raise MarketDataError(
            f"No candle data returned by Bybit for {symbol}."
        )

    candle_items = cast(list[list[object]], raw_list)
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
                f"Malformed candle record from Bybit for {symbol}: {item}"
            ) from error

    # Bybit returns newest first; sort chronologically ascending.
    candles.sort(key=lambda c: c.date)
    return candles

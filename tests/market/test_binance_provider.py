"""Unit tests for the Binance Kline provider with mocked HTTP responses."""

import json
from decimal import Decimal
from typing import Any

import httpx
import pytest

from tradefog.market.providers.binance import fetch_binance_daily_candles
from tradefog.market.types import MarketDataError


def _make_binance_response(
    candle_records: list[Any],
    status_code: int = 200,
) -> httpx.Response:
    """Construct an HTTP response with Binance structure."""
    return httpx.Response(
        status_code=status_code,
        content=json.dumps(candle_records).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )


def test_fetch_binance_spot_candles_success() -> None:
    records = [
        [1725062400000, "58000.0", "59000.0", "57000.0", "58900.0", "12"],
        [1725148800000, "59000.0", "60000.0", "58000.0", "59500.0", "10"],
    ]

    def handler(request: httpx.Request) -> httpx.Response:
        assert "api.binance.com" in request.url.host
        assert request.url.params["symbol"] == "BTCUSDT"
        assert request.url.params["interval"] == "1d"
        return _make_binance_response(records)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    candles = fetch_binance_daily_candles("BTC/USDT", client=client)

    assert len(candles) == 2
    assert candles[0].open == Decimal("58000.0")
    assert candles[0].high == Decimal("59000.0")
    assert candles[1].open == Decimal("59000.0")
    assert candles[1].close == Decimal("59500.0")


def test_fetch_binance_futures_candles() -> None:
    records = [
        [1725148800000, "59000.0", "60000.0", "58000.0", "59500.0", "10"],
    ]

    def handler(request: httpx.Request) -> httpx.Response:
        assert "fapi.binance.com" in request.url.host
        assert request.url.params["symbol"] == "BTCUSDT"
        return _make_binance_response(records)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    candles = fetch_binance_daily_candles(
        "BTCUSDT", category="perpetual_future", client=client
    )
    assert len(candles) == 1


def test_fetch_binance_http_error() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(status_code=500, content=b"Internal Error")

    client = httpx.Client(transport=httpx.MockTransport(handler))
    with pytest.raises(MarketDataError, match="HTTP 500"):
        fetch_binance_daily_candles("BTCUSDT", client=client)


def test_fetch_binance_timeout_error() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        raise httpx.TimeoutException("Timeout")

    client = httpx.Client(transport=httpx.MockTransport(handler))
    with pytest.raises(MarketDataError, match="timed out"):
        fetch_binance_daily_candles("BTCUSDT", client=client)

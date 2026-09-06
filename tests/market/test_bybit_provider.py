"""Unit tests for the Bybit Kline provider with mocked HTTP responses."""

import json
from decimal import Decimal

import httpx
import pytest

from tradefog.market.providers.bybit import fetch_bybit_daily_candles
from tradefog.market.types import MarketDataError


def _make_bybit_response(
    candle_records: list[list[str]],
    ret_code: int = 0,
    ret_msg: str = "OK",
) -> httpx.Response:
    """Construct an HTTP 200 response with Bybit V5 structure."""
    payload = {
        "retCode": ret_code,
        "retMsg": ret_msg,
        "result": {
            "symbol": "BTCUSDT",
            "category": "spot",
            "list": candle_records,
        },
        "retExtInfo": {},
        "time": 1725200000000,
    }
    return httpx.Response(
        status_code=200,
        content=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )


def test_fetch_bybit_daily_candles_success() -> None:
    # 2 sample candles in Bybit reverse chronological order (newest first)
    records = [
        ["1725148800000", "59000.0", "60000.0", "58000.0", "59500.0", "10"],
        ["1725062400000", "58000.0", "59000.0", "57000.0", "58900.0", "12"],
    ]

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["symbol"] == "BTCUSDT"
        assert request.url.params["category"] == "spot"
        assert request.url.params["interval"] == "D"
        return _make_bybit_response(records)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    candles = fetch_bybit_daily_candles("BTCUSDT", client=client)

    assert len(candles) == 2
    # Ascending order check: earliest first
    assert candles[0].open == Decimal("58000.0")
    assert candles[0].high == Decimal("59000.0")
    assert candles[1].open == Decimal("59000.0")
    assert candles[1].close == Decimal("59500.0")


def test_fetch_bybit_daily_candles_linear_category() -> None:
    records = [
        ["1725148800000", "59000.0", "60000.0", "58000.0", "59500.0", "10"],
    ]

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["category"] == "linear"
        return _make_bybit_response(records)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    candles = fetch_bybit_daily_candles(
        "BTCUSDT", category="linear", client=client
    )
    assert len(candles) == 1


def test_fetch_bybit_api_error_retcode() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return _make_bybit_response(
            [], ret_code=10001, ret_msg="Invalid symbol"
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))
    with pytest.raises(MarketDataError, match="Bybit API error 10001"):
        fetch_bybit_daily_candles("UNKNOWN", client=client)


def test_fetch_bybit_http_error_status() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(status_code=500, content=b"Server Error")

    client = httpx.Client(transport=httpx.MockTransport(handler))
    with pytest.raises(MarketDataError, match="HTTP 500"):
        fetch_bybit_daily_candles("BTCUSDT", client=client)


def test_fetch_bybit_timeout_error() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        raise httpx.TimeoutException("Connection timed out")

    client = httpx.Client(transport=httpx.MockTransport(handler))
    with pytest.raises(MarketDataError, match="timed out"):
        fetch_bybit_daily_candles("BTCUSDT", client=client)

"""Unit tests for the Yahoo Finance chart provider with mocked HTTP responses."""

import json
from collections.abc import Sequence
from decimal import Decimal

import httpx
import pytest

from tradefog.market.providers.yfinance import fetch_yfinance_daily_candles
from tradefog.market.types import MarketDataError


def _make_yfinance_response(
    timestamps: Sequence[int],
    opens: Sequence[float | None],
    highs: Sequence[float | None],
    lows: Sequence[float | None],
    closes: Sequence[float | None],
    status_code: int = 200,
) -> httpx.Response:
    """Construct an HTTP response with Yahoo Finance chart structure."""
    payload = {
        "chart": {
            "result": [
                {
                    "meta": {"symbol": "AAPL"},
                    "timestamp": timestamps,
                    "indicators": {
                        "quote": [
                            {
                                "open": opens,
                                "high": highs,
                                "low": lows,
                                "close": closes,
                            }
                        ]
                    },
                }
            ],
            "error": None,
        }
    }
    return httpx.Response(
        status_code=status_code,
        content=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )


def test_fetch_yfinance_daily_candles_success() -> None:
    timestamps = [1725062400, 1725148800]
    opens = [220.5, 222.0]
    highs = [225.0, 224.5]
    lows = [219.0, 221.0]
    closes = [223.5, 224.0]

    def handler(request: httpx.Request) -> httpx.Response:
        assert "AAPL" in str(request.url)
        return _make_yfinance_response(timestamps, opens, highs, lows, closes)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    candles = fetch_yfinance_daily_candles("AAPL", client=client)

    assert len(candles) == 2
    assert candles[0].open == Decimal("220.5")
    assert candles[0].high == Decimal("225.0")
    assert candles[1].close == Decimal("224.0")


def test_fetch_yfinance_skips_null_data() -> None:
    timestamps = [1725062400, 1725148800]
    opens = [None, 222.0]
    highs = [None, 224.5]
    lows = [None, 221.0]
    closes = [None, 224.0]

    def handler(_request: httpx.Request) -> httpx.Response:
        return _make_yfinance_response(timestamps, opens, highs, lows, closes)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    candles = fetch_yfinance_daily_candles("AAPL", client=client)

    assert len(candles) == 1
    assert candles[0].close == Decimal("224.0")


def test_fetch_yfinance_http_error() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(status_code=404, content=b"Not Found")

    client = httpx.Client(transport=httpx.MockTransport(handler))
    with pytest.raises(MarketDataError, match="HTTP 404"):
        fetch_yfinance_daily_candles("INVALID", client=client)

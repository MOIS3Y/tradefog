"""Unit tests for the market service using mocked HTTP clients."""

import datetime
import json
from decimal import Decimal

import httpx
import pytest

from tradefog.market.service import fetch_atr_context, fetch_bybit_atr_context
from tradefog.market.types import MarketDataError


def _make_sample_bybit_payload(
    base_date: datetime.date, count: int = 20
) -> dict[str, object]:
    """Generate mock Bybit JSON with descending dates."""
    records: list[list[str]] = []
    for i in range(count - 1, -1, -1):
        day = base_date + datetime.timedelta(days=i)
        ts_ms = int(
            datetime.datetime.combine(
                day, datetime.time.min, tzinfo=datetime.UTC
            ).timestamp()
            * 1000
        )
        records.append(
            [str(ts_ms), "100.00", "110.00", "100.00", "105.00", "50"]
        )
    return {
        "retCode": 0,
        "retMsg": "OK",
        "result": {
            "symbol": "BTCUSDT",
            "category": "spot",
            "list": records,
        },
        "time": 1725200000000,
    }


def _make_sample_binance_payload(
    base_date: datetime.date, count: int = 20
) -> list[list[object]]:
    """Generate mock Binance JSON with ascending dates."""
    records: list[list[object]] = []
    for i in range(count):
        day = base_date + datetime.timedelta(days=i)
        ts_ms = int(
            datetime.datetime.combine(
                day, datetime.time.min, tzinfo=datetime.UTC
            ).timestamp()
            * 1000
        )
        records.append(
            [ts_ms, "100.00", "110.00", "100.00", "105.00", "50", ts_ms + 86400000]
        )
    return records


def test_fetch_bybit_atr_context_success() -> None:
    trade_date = datetime.date(2026, 8, 20)
    base_date = datetime.date(2026, 8, 1)
    payload = _make_sample_bybit_payload(base_date, count=21)

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            status_code=200,
            content=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))
    context = fetch_bybit_atr_context(
        "BTCUSDT",
        product_kind="spot",
        trade_date=trade_date,
        client=client,
    )

    assert context.atr_value == Decimal("10.00")
    assert context.contributing_date == datetime.date(2026, 8, 19)
    assert len(context.candles) == 14
    assert context.observed_session_range == Decimal("10.00")
    assert context.session_range_percent == Decimal("100.00")


def test_fetch_binance_atr_context_success() -> None:
    trade_date = datetime.date(2026, 8, 20)
    base_date = datetime.date(2026, 8, 1)
    payload = _make_sample_binance_payload(base_date, count=21)

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            status_code=200,
            content=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))
    context = fetch_atr_context(
        provider="binance",
        symbol="BTCUSDT",
        product_kind="spot",
        trade_date=trade_date,
        client=client,
    )

    assert context.atr_value == Decimal("10.00")
    assert context.contributing_date == datetime.date(2026, 8, 19)
    assert len(context.candles) == 14


def test_fetch_unsupported_provider_raises_error() -> None:
    with pytest.raises(MarketDataError, match="Unsupported or manual-only"):
        fetch_atr_context(
            provider="unknown_provider",
            symbol="BTCUSDT",
        )


def test_fetch_bybit_atr_context_insufficient_candles() -> None:
    trade_date = datetime.date(2026, 8, 5)
    base_date = datetime.date(2026, 8, 1)
    payload = _make_sample_bybit_payload(base_date, count=5)

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            status_code=200,
            content=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))
    with pytest.raises(MarketDataError, match="Insufficient closed daily"):
        fetch_bybit_atr_context(
            "BTCUSDT",
            trade_date=trade_date,
            client=client,
        )

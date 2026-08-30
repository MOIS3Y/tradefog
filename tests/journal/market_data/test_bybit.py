"""Tests for the public Bybit V5 response boundary."""

from datetime import UTC, date, datetime

import httpx

from tradefog.accounts.models import User
from tradefog.journal.market_data.providers.bybit import fetch_daily_data
from tradefog.journal.models import Asset, ProfileTradingPair, TradingProfile


def create_pair() -> ProfileTradingPair:
    """Create an unsaved pair graph sufficient for request mapping."""
    owner = User(username="trader")
    quote = Asset(owner=owner, symbol="USDT")
    base = Asset(owner=owner, symbol="BTC")
    profile = TradingProfile(
        owner=owner,
        capital_asset=quote,
        market_type=TradingProfile.MarketType.SPOT.value,
    )
    return ProfileTradingPair(profile=profile, asset=base)


def test_bybit_separates_closed_and_current_daily_candles() -> None:
    """The open UTC day must never enter persisted ATR history."""
    day_29 = int(datetime(2026, 8, 29, tzinfo=UTC).timestamp() * 1000)
    day_30 = int(datetime(2026, 8, 30, tzinfo=UTC).timestamp() * 1000)
    server_time = int(datetime(2026, 8, 30, 12, tzinfo=UTC).timestamp() * 1000)

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["category"] == "spot"
        assert request.url.params["symbol"] == "BTCUSDT"
        return httpx.Response(
            200,
            json={
                "retCode": 0,
                "time": server_time,
                "result": {
                    "list": [
                        [str(day_30), "100", "105", "98", "103"],
                        [str(day_29), "99", "102", "97", "100"],
                    ]
                },
            },
        )

    with httpx.Client(
        base_url="https://api.bybit.test",
        transport=httpx.MockTransport(handler),
    ) as client:
        result = fetch_daily_data(
            create_pair(),
            date(2026, 8, 30),
            client=client,
        )

    assert [c.trading_date for c in result.closed_candles] == [
        date(2026, 8, 29)
    ]
    assert result.current_session is not None
    assert result.current_session.trading_date == date(2026, 8, 30)

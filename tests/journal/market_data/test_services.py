"""Tests for date selection, cache fallback, and ATR snapshots."""

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from unittest.mock import patch

import httpx
from django.core.exceptions import ValidationError
from pytest import mark, raises

from tradefog.accounts.models import User
from tradefog.journal.market_data.services import (
    get_market_context,
    refresh_market_context,
)
from tradefog.journal.market_data.types import CandleValue, ProviderDailyData
from tradefog.journal.models import (
    Asset,
    DailyCandle,
    MarketDataState,
    ProfileTradingPair,
    Trade,
    TradingProfile,
)
from tradefog.journal.services import submit_trade


def create_pair(*, provider: str = "MANUAL") -> ProfileTradingPair:
    """Create one persisted spot pair with an owned risk profile."""
    owner = User.objects.create_user(username="trader")
    quote = Asset.objects.create(owner=owner, symbol="USDT")
    base = Asset.objects.create(owner=owner, symbol="BTC")
    profile = TradingProfile.objects.create(
        owner=owner,
        name="Primary",
        capital_asset=quote,
        initial_capital=Decimal(10000),
        risk_stop_capital=Decimal(9000),
    )
    return ProfileTradingPair.objects.create(
        profile=profile,
        asset=base,
        price_step=Decimal(1),
        quantity_step=Decimal("0.01"),
        market_data_provider=provider,
    )


def create_flat_history(pair: ProfileTradingPair, start: date) -> None:
    """Store fifteen candles whose True Range is always four."""
    for offset in range(15):
        _ = DailyCandle.objects.create(
            trading_pair=pair,
            trading_date=start + timedelta(days=offset),
            open_price=Decimal(100),
            high_price=Decimal(102),
            low_price=Decimal(98),
            close_price=Decimal(100),
        )


@mark.django_db
def test_daily_candle_requires_coherent_ohlc_range() -> None:
    """Manual and provider facts share the same price-range invariant."""
    pair = create_pair()
    candle = DailyCandle(
        trading_pair=pair,
        trading_date=date(2026, 8, 1),
        open_price=Decimal(120),
        high_price=Decimal(110),
        low_price=Decimal(90),
        close_price=Decimal(100),
    )

    with raises(ValidationError):
        candle.full_clean()


@mark.django_db
def test_context_uses_only_candles_before_trade_date() -> None:
    """The selected session cannot leak into its opening ATR value."""
    pair = create_pair()
    start = date(2026, 8, 1)
    create_flat_history(pair, start)
    trade_date = start + timedelta(days=15)
    _ = DailyCandle.objects.create(
        trading_pair=pair,
        trading_date=trade_date,
        open_price=Decimal(100),
        high_price=Decimal(200),
        low_price=Decimal(1),
        close_price=Decimal(100),
    )

    context = get_market_context(pair, trade_date)

    assert context.atr_value == Decimal(4)
    assert context.atr_as_of_date == trade_date - timedelta(days=1)
    assert len(context.chart_candles) == 14
    assert context.chart_candles[-1].trading_date == trade_date - timedelta(
        days=1
    )
    assert all(
        candle.trading_date < trade_date for candle in context.chart_candles
    )
    assert context.candle_chart_data[-1]["close"] == "100"


@mark.django_db
def test_context_keeps_current_session_range_separate() -> None:
    """An open-session observation is compared with but excluded from ATR."""
    pair = create_pair(provider="BYBIT")
    start = date(2026, 8, 1)
    create_flat_history(pair, start)
    trade_date = start + timedelta(days=15)
    observed_at = datetime(2026, 8, 16, 12, tzinfo=UTC)
    _ = MarketDataState.objects.create(
        trading_pair=pair,
        current_session_date=trade_date,
        current_high=Decimal(102),
        current_low=Decimal(99),
        current_observed_at=observed_at,
        last_success_at=observed_at,
    )

    context = get_market_context(pair, trade_date)

    assert context.atr_value == Decimal(4)
    assert context.session_range == Decimal(3)
    assert context.session_range_percent == Decimal(75)


@mark.django_db
def test_zero_atr_does_not_divide_current_range_by_zero() -> None:
    """A flat closed history keeps the live range comparison undefined."""
    pair = create_pair(provider="BYBIT")
    start = date(2026, 8, 1)
    for offset in range(15):
        _ = DailyCandle.objects.create(
            trading_pair=pair,
            trading_date=start + timedelta(days=offset),
            open_price=Decimal(100),
            high_price=Decimal(100),
            low_price=Decimal(100),
            close_price=Decimal(100),
        )
    trade_date = start + timedelta(days=15)
    observed_at = datetime(2026, 8, 16, 12, tzinfo=UTC)
    _ = MarketDataState.objects.create(
        trading_pair=pair,
        current_session_date=trade_date,
        current_high=Decimal(101),
        current_low=Decimal(99),
        current_observed_at=observed_at,
        last_success_at=observed_at,
    )

    context = get_market_context(pair, trade_date)

    assert context.atr_value == 0
    assert context.session_range == 2
    assert context.session_range_percent is None


@mark.django_db
def test_provider_failure_returns_cached_context_and_marks_it_stale() -> None:
    """A failed refresh must retain usable stored ATR history."""
    pair = create_pair(provider="BYBIT")
    start = date(2026, 8, 1)
    create_flat_history(pair, start)

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(503)

    with httpx.Client(
        base_url="https://api.bybit.test",
        transport=httpx.MockTransport(handler),
    ) as client:
        context = refresh_market_context(
            pair,
            start + timedelta(days=15),
            client=client,
        )

    assert context.atr_value == Decimal(4)
    assert context.is_stale is True
    assert DailyCandle.objects.filter(trading_pair=pair).count() == 15


@mark.django_db
def test_successful_refresh_preserves_manual_correction() -> None:
    """Provider updates fill cache gaps without replacing manual facts."""
    pair = create_pair(provider="BYBIT")
    candle_date = date(2026, 8, 1)
    manual = DailyCandle.objects.create(
        trading_pair=pair,
        trading_date=candle_date,
        open_price=Decimal(100),
        high_price=Decimal(110),
        low_price=Decimal(90),
        close_price=Decimal(105),
    )
    observed_at = datetime(2026, 8, 3, 12, tzinfo=UTC)
    _ = MarketDataState.objects.create(
        trading_pair=pair,
        current_session_date=candle_date,
        current_high=Decimal(109),
        current_low=Decimal(91),
        current_observed_at=observed_at - timedelta(days=2),
    )
    provider_data = ProviderDailyData(
        closed_candles=(
            CandleValue(
                trading_date=candle_date,
                open_price=Decimal(200),
                high_price=Decimal(210),
                low_price=Decimal(190),
                close_price=Decimal(205),
                source="BYBIT",
            ),
            CandleValue(
                trading_date=candle_date + timedelta(days=1),
                open_price=Decimal(105),
                high_price=Decimal(112),
                low_price=Decimal(101),
                close_price=Decimal(110),
                source="BYBIT",
            ),
        ),
        current_session=None,
        observed_at=observed_at,
    )

    with patch(
        "tradefog.journal.market_data.services.fetch_daily_data",
        return_value=provider_data,
    ):
        _ = refresh_market_context(pair, date(2026, 8, 3))

    manual.refresh_from_db()
    provider_candle = DailyCandle.objects.get(
        trading_pair=pair,
        trading_date=candle_date + timedelta(days=1),
    )
    assert manual.close_price == Decimal(105)
    assert manual.source == "MANUAL"
    assert provider_candle.source == "BYBIT"
    state = MarketDataState.objects.get(trading_pair=pair)
    assert state.current_session_date is None


@mark.django_db
def test_submit_freezes_cached_context_without_network_io() -> None:
    """Submission snapshots stored observations and does not refresh Bybit."""
    pair = create_pair(provider="BYBIT")
    start = date(2026, 8, 1)
    create_flat_history(pair, start)
    _ = DailyCandle.objects.filter(
        trading_pair=pair,
        trading_date=start + timedelta(days=14),
    ).update(
        high_price=Decimal(107),
        low_price=Decimal(93),
    )
    trade_date = start + timedelta(days=15)
    observed_at = datetime(2026, 8, 16, 12, tzinfo=UTC)
    _ = MarketDataState.objects.create(
        trading_pair=pair,
        current_session_date=trade_date,
        current_high=Decimal(102),
        current_low=Decimal(99),
        current_observed_at=observed_at,
        last_success_at=observed_at,
    )
    trade = Trade.objects.create(
        profile=pair.profile,
        trading_pair=pair,
        trade_date=trade_date,
        direction=Trade.Direction.LONG.value,
        planned_entry=Decimal(100),
        planned_stop=Decimal(95),
    )

    submitted = submit_trade(trade)

    assert submitted.atr_value_snapshot == Decimal("4.714285714286")
    assert submitted.atr_as_of_date_snapshot == trade_date - timedelta(days=1)
    assert submitted.session_range_snapshot == Decimal(3)
    assert submitted.session_range_percent_snapshot == Decimal("63.6364")

    submitted.trade_date = trade_date + timedelta(days=2)
    submitted.save(update_fields=["trade_date", "updated_at"])
    submitted.refresh_from_db()
    assert submitted.atr_as_of_date_snapshot == trade_date - timedelta(days=1)

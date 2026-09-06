"""Tests for trade creation, workspace, position planning, and HTMX endpoints."""

import datetime
import json
from decimal import Decimal
from unittest.mock import patch

import httpx
from django.test import Client
from django.urls import reverse
from django.utils.translation import override
from pytest import mark

from tradefog.accounts.models import User
from tradefog.journal.models import (
    Asset,
    StrategyCapital,
    Trade,
    TradingPair,
    TradingProfile,
    TradingStrategy,
    Venue,
    VenueInstrument,
    VenueWalletAsset,
    Wallet,
    WalletAsset,
    WalletOperation,
)
from tradefog.journal.models.enums import (
    Direction,
    ProductKind,
    TradeStatus,
    WalletOperationKind,
)

PASSWORD = "correct-horse-battery-staple"


def _setup_trade_environment(
    username: str = "trader",
) -> tuple[
    Client,
    User,
    TradingProfile,
    TradingStrategy,
    VenueInstrument,
    WalletAsset,
]:
    """Create a complete fixture hierarchy for trade tests."""
    user = User.objects.create_user(username=username, password=PASSWORD)
    client = Client()
    client.force_login(user)

    btc = Asset.objects.create(
        symbol="BTC", name="Bitcoin", asset_type="crypto"
    )
    usdt = Asset.objects.create(
        symbol="USDT", name="Tether", asset_type="crypto"
    )
    pair = TradingPair.objects.create(
        base=btc, quote=usdt, canonical_symbol="BTC/USDT"
    )

    venue = Venue.objects.create(name="Bybit", is_active=True)
    instrument = VenueInstrument.objects.create(
        venue=venue,
        pair=pair,
        product=ProductKind.SPOT,
        exec_symbol="BTCUSDT",
        price_step=Decimal("0.01"),
        qty_step=Decimal("0.001"),
        min_qty=Decimal("0.001"),
        min_notional=Decimal("5.00"),
        is_active=True,
    )
    venue_usdt = VenueWalletAsset.objects.create(
        venue=venue, asset=usdt, is_active=True
    )

    profile = TradingProfile.objects.create(
        owner=user, name="Main", venue=venue, is_archived=False
    )
    wallet = Wallet.objects.create(profile=profile)
    wallet_usdt = WalletAsset.objects.create(
        wallet=wallet,
        venue_wallet_asset=venue_usdt,
        risk_stop_capital=Decimal(1000),
        is_archived=False,
    )
    WalletOperation.objects.create(
        wallet_asset=wallet_usdt,
        kind=WalletOperationKind.DEPOSIT,
        amount=Decimal(10000),
    )

    strategy = TradingStrategy.objects.create(
        profile=profile,
        name="Breakout",
        risk_percent=Decimal("1.00"),
        reward_multiple=Decimal("3.00"),
        is_archived=False,
    )
    StrategyCapital.objects.create(
        strategy=strategy,
        wallet_asset=wallet_usdt,
        capital=Decimal("5000.00"),
        is_archived=False,
    )

    return client, user, profile, strategy, instrument, wallet_usdt


@mark.django_db
def test_trade_create_get_renders_workspace() -> None:
    client, _user, _profile, _strategy, _instrument, _w_asset = (
        _setup_trade_environment()
    )
    with override("en"):
        response = client.get(reverse("journal:trade_create"))

    assert response.status_code == 200
    content = response.content.decode()
    assert "New trade draft" in content
    assert "Main" in content


@mark.django_db
def test_trade_create_post_creates_draft_and_redirects() -> None:
    client, _user, profile, strategy, instrument, _w_asset = (
        _setup_trade_environment()
    )
    with override("en"):
        response = client.post(
            reverse("journal:trade_create"),
            {
                "profile": profile.pk,
                "strategy": strategy.pk,
                "venue_instrument": instrument.pk,
                "trade_date": "2026-09-02",
                "direction": "long",
                "planned_entry": "60000.00",
                "planned_stop": "58000.00",
            },
        )

    assert response.status_code == 302
    assert Trade.objects.filter(profile=profile).count() == 1
    trade = Trade.objects.first()
    assert trade is not None
    assert trade.status == TradeStatus.DRAFT
    assert trade.direction == Direction.LONG


@mark.django_db
def test_trade_options_cascading_endpoint() -> None:
    client, _user, profile, strategy, _instrument, _w_asset = (
        _setup_trade_environment()
    )
    with override("en"):
        response = client.get(
            reverse("journal:trade_options"),
            {"profile": profile.pk, "strategy": strategy.pk},
        )

    assert response.status_code == 200
    content = response.content.decode()
    assert "Breakout" in content
    assert "BTC/USDT" in content


@mark.django_db
def test_trade_plan_preview_calculates_1_to_3_plan() -> None:
    client, _user, _profile, strategy, instrument, _w_asset = (
        _setup_trade_environment()
    )
    # Allocation 5000, risk 1% = 50.00 USDT
    # Entry 60000, Stop 58000 -> Distance 2000
    # Take profit = 60000 + 2000 * 3 = 66000
    # Quantity = 50 / 2000 = 0.025 BTC (step 0.001)
    # Notional = 60000 * 0.025 = 1500 USDT
    # Planned risk = 0.025 * 2000 = 50.00 USDT
    # Planned profit = 50 * 3 = 150.00 USDT
    with override("en"):
        response = client.post(
            reverse("journal:trade_plan_preview"),
            {
                "strategy": strategy.pk,
                "venue_instrument": instrument.pk,
                "direction": "long",
                "planned_entry": "60000.00",
                "planned_stop": "58000.00",
            },
        )

    assert response.status_code == 200
    content = response.content.decode()
    assert "50 USDT" in content  # Planned risk
    assert "150 USDT" in content  # Planned profit
    assert "66000" in content  # Take profit
    assert "0.025" in content  # Quantity
    assert "BTC" in content
    assert "1500 USDT" in content  # Position value


@mark.django_db
def test_trade_plan_preview_uses_custom_strategy_reward_multiple() -> None:
    client, _user, _profile, strategy, instrument, _w_asset = (
        _setup_trade_environment()
    )
    strategy.reward_multiple = Decimal("2.50")
    strategy.save()

    # Entry 60000, Stop 58000 -> Distance 2000
    # Take profit = 60000 + 2000 * 2.5 = 65000
    # Planned risk = 50.00 USDT
    # Planned profit = 50 * 2.5 = 125.00 USDT
    with override("en"):
        response = client.post(
            reverse("journal:trade_plan_preview"),
            {
                "strategy": strategy.pk,
                "venue_instrument": instrument.pk,
                "direction": "long",
                "planned_entry": "60000.00",
                "planned_stop": "58000.00",
            },
        )

    assert response.status_code == 200
    content = response.content.decode()
    assert "50 USDT" in content
    assert "125 USDT" in content
    assert "65000" in content


@mark.django_db
def test_trade_plan_preview_warns_on_price_step_misalignment() -> None:
    client, _user, _profile, strategy, instrument, _w_asset = (
        _setup_trade_environment()
    )
    with override("en"):
        response = client.post(
            reverse("journal:trade_plan_preview"),
            {
                "strategy": strategy.pk,
                "venue_instrument": instrument.pk,
                "direction": "long",
                "planned_entry": "60000.005",  # Misaligned for step 0.01
                "planned_stop": "58000.00",
            },
        )

    assert response.status_code == 200
    content = response.content.decode()
    assert "Entry must be aligned" in content


@mark.django_db
def test_trade_plan_preview_warns_on_insufficient_wallet_capacity() -> None:
    client, _user, _profile, strategy, instrument, wallet_usdt = (
        _setup_trade_environment()
    )
    # Withdraw most funds so only 100 USDT is available
    WalletOperation.objects.create(
        wallet_asset=wallet_usdt,
        kind=WalletOperationKind.WITHDRAWAL,
        amount=Decimal(9900),
    )

    with override("en"):
        response = client.post(
            reverse("journal:trade_plan_preview"),
            {
                "strategy": strategy.pk,
                "venue_instrument": instrument.pk,
                "direction": "long",
                "planned_entry": "60000.00",
                "planned_stop": "58000.00",
            },
        )

    assert response.status_code == 200
    content = response.content.decode()
    assert "exceeds available wallet funds" in content


@mark.django_db
def test_trade_market_preview_with_mocked_bybit() -> None:
    client, _user, _profile, _strategy, instrument, _w_asset = (
        _setup_trade_environment()
    )

    sample_records: list[list[str]] = []
    base_date = datetime.date(2026, 8, 1)
    for i in range(20, -1, -1):
        day = base_date + datetime.timedelta(days=i)
        ts_ms = int(
            datetime.datetime.combine(
                day, datetime.time.min, tzinfo=datetime.UTC
            ).timestamp()
            * 1000
        )
        sample_records.append(
            [str(ts_ms), "60000.00", "62000.00", "59000.00", "61000.00", "50"]
        )

    mock_payload = {
        "retCode": 0,
        "retMsg": "OK",
        "result": {
            "symbol": "BTCUSDT",
            "category": "spot",
            "list": sample_records,
        },
        "time": 1725200000000,
    }

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            status_code=200,
            content=json.dumps(mock_payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )

    mock_client = httpx.Client(transport=httpx.MockTransport(handler))

    with patch(
        "tradefog.market.providers.bybit.httpx.Client"
    ) as mock_client_cls:
        mock_client_cls.return_value.__enter__.return_value = mock_client
        with override("en"):
            response = client.post(
                reverse("journal:trade_market_preview"),
                {
                    "venue_instrument": instrument.pk,
                    "trade_date": "2026-08-20",
                    "planned_entry": "60000.00",
                    "planned_stop": "58000.00",
                },
            )

    assert response.status_code == 200
    content = response.content.decode()
    assert "ATR(14)" in content


@mark.django_db
def test_trade_checklist_preview() -> None:
    client, _user, _profile, _strategy, _instrument, _w_asset = (
        _setup_trade_environment()
    )
    with override("en"):
        response = client.post(
            reverse("journal:trade_checklist_preview"),
            {
                "market_sentiment": "POSITIVE",
                "information_background": "POSITIVE",
                "global_daily_direction": "POSITIVE",
                "local_daily_movement": "POSITIVE",
                "direction": "LONG",
            },
        )

    assert response.status_code == 200
    content = response.content.decode()
    assert "4 of 4" in content
    assert "Direction agrees with the checklist" in content


@mark.django_db
def test_trade_options_filters_by_product_kind() -> None:
    client, _user, profile, strategy, _instrument, _w_asset = (
        _setup_trade_environment()
    )
    # Add a perpetual futures instrument on the same venue
    usdt = _w_asset.venue_wallet_asset.asset
    eth = Asset.objects.create(
        symbol="ETH", name="Ethereum", asset_type="crypto"
    )
    eth_usdt = TradingPair.objects.create(
        base=eth, quote=usdt, canonical_symbol="ETH/USDT"
    )
    _futures_inst = VenueInstrument.objects.create(
        venue=profile.venue,
        pair=eth_usdt,
        product=ProductKind.PERPETUAL_FUTURE,
        exec_symbol="ETHUSDT",
        price_step=Decimal("0.05"),
        qty_step=Decimal("0.01"),
        min_qty=Decimal("0.01"),
        min_notional=Decimal("5.00"),
        is_active=True,
    )

    with override("en"):
        # Select spot product kind
        response_spot = client.get(
            reverse("journal:trade_options"),
            {
                "profile": profile.pk,
                "strategy": strategy.pk,
                "product_kind": "spot",
            },
        )
        # Select perpetual future product kind
        response_futures = client.get(
            reverse("journal:trade_options"),
            {
                "profile": profile.pk,
                "strategy": strategy.pk,
                "product_kind": "perpetual_future",
            },
        )

    assert response_spot.status_code == 200
    content_spot = response_spot.content.decode()
    assert "BTC/USDT" in content_spot
    assert "ETH/USDT" not in content_spot

    assert response_futures.status_code == 200
    content_futures = response_futures.content.decode()
    assert "ETH/USDT" in content_futures
    assert "BTC/USDT" not in content_futures


@mark.django_db
def test_trade_plan_preview_empty_inputs_renders_placeholder() -> None:
    client, _user, _profile, _strategy, _instrument, _w_asset = (
        _setup_trade_environment()
    )
    with override("en"):
        response = client.post(
            reverse("journal:trade_plan_preview"),
            {},
        )

    assert response.status_code == 200
    content = response.content.decode()
    assert "Position plan not calculated" in content
    assert "Enter planned entry and stop" in content


@mark.django_db
def test_trade_checklist_preview_initial_neutral_gauge() -> None:
    client, _user, _profile, _strategy, _instrument, _w_asset = (
        _setup_trade_environment()
    )
    with override("en"):
        response = client.post(
            reverse("journal:trade_checklist_preview"),
            {},
        )

    assert response.status_code == 200
    content = response.content.decode()
    assert "0 of 4" in content
    assert "--tf-gauge-position: 50%" in content

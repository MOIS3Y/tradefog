"""Tests for trade creation, workspace, and reactive JSON endpoints."""

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
    MarketDataProvider,
    ProductKind,
    TradeStatus,
    WalletOperationKind,
)

PASSWORD = "correct-horse-battery-staple"


def _setup_trade_environment(
    username: str = "trader",
    market_data_provider: str = MarketDataProvider.BYBIT,
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

    venue = Venue.objects.create(
        name="Bybit",
        market_data_provider=market_data_provider,
        is_active=True,
    )
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
    assert "trade-workspace-config" in content


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
    assert trade.draft_context["planned_entry"] == "60000.00"
    assert trade.draft_context["planned_stop"] == "58000.00"

    # Verify workspace detail view renders with review and attachments
    detail_res = client.get(
        reverse("journal:trade_workspace", kwargs={"pk": trade.pk})
    )
    assert detail_res.status_code == 200
    assert "Trade notes & review" in detail_res.content.decode()


@mark.django_db
def test_trade_workspace_options_json_endpoint() -> None:
    client, _user, profile, strategy, instrument, _w_asset = (
        _setup_trade_environment()
    )
    response = client.get(
        reverse("journal:trade_workspace_options"),
        {"profile": profile.pk, "strategy": strategy.pk},
    )

    assert response.status_code == 200
    data = response.json()
    assert "strategies" in data
    assert "instruments" in data
    assert data["selected_strategy_id"] == strategy.pk
    assert data["selected_instrument_id"] == instrument.pk
    assert len(data["instruments"]) == 1
    assert data["instruments"][0]["exec_symbol"] == "BTCUSDT"
    assert data["context_bar"]["profile_name"] == "Main"
    assert data["context_bar"]["venue_name"] == "Bybit"
    assert data["context_bar"]["fixed_1r"] == "50.00"


@mark.django_db
def test_trade_workspace_options_filters_by_strategy_allocations() -> None:
    client, _user, profile, strategy, _instrument, _w_asset = (
        _setup_trade_environment()
    )
    # Add an unallocated asset and trading pair
    sol = Asset.objects.create(symbol="SOL", name="Solana", asset_type="crypto")
    usdc = Asset.objects.create(symbol="USDC", name="USD Coin", asset_type="crypto")
    sol_usdc = TradingPair.objects.create(
        base=sol, quote=usdc, canonical_symbol="SOL/USDC"
    )
    _unallocated_inst = VenueInstrument.objects.create(
        venue=profile.venue,
        pair=sol_usdc,
        product=ProductKind.SPOT,
        exec_symbol="SOLUSDC",
        price_step=Decimal("0.01"),
        qty_step=Decimal("0.01"),
        is_active=True,
    )

    response = client.get(
        reverse("journal:trade_workspace_options"),
        {"profile": profile.pk, "strategy": strategy.pk},
    )

    assert response.status_code == 200
    data = response.json()
    symbols = [inst["canonical_symbol"] for inst in data["instruments"]]
    assert "BTC/USDT" in symbols
    assert "SOL/USDC" not in symbols


@mark.django_db
def test_trade_market_data_with_mocked_bybit() -> None:
    client, _user, _profile, _strategy, instrument, _w_asset = (
        _setup_trade_environment(market_data_provider=MarketDataProvider.BYBIT)
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
        response = client.get(
            reverse("journal:trade_market_data"),
            {
                "instrument": instrument.pk,
                "trade_date": "2026-08-20",
            },
        )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["provider"] == "bybit"
    assert "atr_value" in data
    assert len(data["candles"]) > 0


@mark.django_db
def test_trade_market_data_for_manual_venue_returns_manual_status() -> None:
    client, _user, _profile, _strategy, instrument, _w_asset = (
        _setup_trade_environment(market_data_provider=MarketDataProvider.NONE)
    )
    response = client.get(
        reverse("journal:trade_market_data"),
        {"instrument": instrument.pk, "trade_date": "2026-08-20"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "manual"
    assert data["provider"] == "none"


@mark.django_db
def test_trade_create_without_profile_redirects_to_profiles(
    client: Client,
) -> None:
    user = User.objects.create_user(username="noprofile", password="password")
    client.force_login(user)

    with override("en"):
        response = client.get(reverse("journal:trade_create"))

    assert response.status_code == 302
    assert reverse("journal:profile_overview") in response.headers["Location"]


@mark.django_db
def test_trades_overview_without_profile_renders_no_profile_modal(
    client: Client,
) -> None:
    user = User.objects.create_user(username="noprofile2", password="password")
    client.force_login(user)

    with override("en"):
        response = client.get(reverse("journal:trades"))

    assert response.status_code == 200
    content = response.content.decode()
    assert "no-profile-modal" in content
    assert "Trading profile required" in content


@mark.django_db
def test_trade_delete_draft_success() -> None:
    client, _user, profile, strategy, instrument, _w_asset = (
        _setup_trade_environment()
    )
    trade = Trade.objects.create(
        profile=profile,
        strategy=strategy,
        venue_instrument=instrument,
        trade_date=datetime.date(2026, 9, 6),
        direction=Direction.LONG,
    )

    # GET returns confirmation modal form
    get_res = client.get(
        reverse("journal:trade_delete", kwargs={"pk": trade.pk})
    )
    assert get_res.status_code == 200
    assert "Delete draft" in get_res.content.decode()

    # Standard POST deletes draft and redirects to overview
    post_res = client.post(
        reverse("journal:trade_delete", kwargs={"pk": trade.pk})
    )
    assert post_res.status_code == 302
    assert post_res.headers["Location"] == reverse("journal:trades")
    assert not Trade.objects.filter(pk=trade.pk).exists()

    # HTMX POST deletes draft and returns trade results table
    trade2 = Trade.objects.create(
        profile=profile,
        strategy=strategy,
        venue_instrument=instrument,
        trade_date=datetime.date(2026, 9, 6),
        direction=Direction.LONG,
    )
    htmx_res = client.post(
        reverse("journal:trade_delete", kwargs={"pk": trade2.pk}),
        headers={"HX-Request": "true"},
    )
    assert htmx_res.status_code == 200
    assert not Trade.objects.filter(pk=trade2.pk).exists()
    assert "tradefog:toast" in htmx_res.headers.get("HX-Trigger", "")


@mark.django_db
def test_cannot_delete_non_draft_trade() -> None:
    client, _user, profile, strategy, instrument, _w_asset = (
        _setup_trade_environment()
    )
    trade = Trade.objects.create(
        profile=profile,
        strategy=strategy,
        venue_instrument=instrument,
        trade_date=datetime.date(2026, 9, 6),
        direction=Direction.LONG,
        status=TradeStatus.OPEN,
    )

    post_res = client.post(
        reverse("journal:trade_delete", kwargs={"pk": trade.pk}),
        headers={"HX-Request": "true"},
    )
    assert post_res.status_code == 409
    assert Trade.objects.filter(pk=trade.pk).exists()


@mark.django_db
def test_save_trade_draft_preserves_notes_and_context() -> None:
    client, _user, profile, strategy, instrument, _w_asset = (
        _setup_trade_environment()
    )
    trade = Trade.objects.create(
        profile=profile,
        strategy=strategy,
        venue_instrument=instrument,
        trade_date=datetime.date(2026, 9, 6),
        direction=Direction.LONG,
        description_markdown="Important analysis: key resistance level held.",
    )

    post_res = client.post(
        reverse("journal:trade_workspace", kwargs={"pk": trade.pk}),
        {
            "profile": profile.pk,
            "strategy": strategy.pk,
            "trade_date": "2026-09-07",
            "venue_instrument": instrument.pk,
            "direction": "long",
            "planned_entry": "51000.00",
            "planned_stop": "49500.00",
            "market_sentiment": "POSITIVE",
            "global_daily_direction": "POSITIVE",
        },
    )
    assert post_res.status_code == 302
    trade.refresh_from_db()
    assert trade.trade_date == datetime.date(2026, 9, 7)
    assert trade.direction == Direction.LONG
    assert trade.draft_context["planned_entry"] == "51000.00"
    assert trade.draft_context["planned_stop"] == "49500.00"
    assert trade.draft_context["market_sentiment"] == "POSITIVE"
    assert (
        trade.description_markdown
        == "Important analysis: key resistance level held."
    )

    # GET response populates form fields and checklist inputs
    get_res = client.get(
        reverse("journal:trade_workspace", kwargs={"pk": trade.pk})
    )
    assert get_res.status_code == 200
    content = get_res.content.decode()
    assert 'value="51000.00"' in content
    assert 'value="49500.00"' in content
    assert "trade-workspace-config" in content


@mark.django_db
def test_trade_workspace_read_only_mode_for_pending_trade() -> None:
    client, _user, profile, strategy, instrument, _w_asset = (
        _setup_trade_environment()
    )
    trade = Trade.objects.create(
        profile=profile,
        strategy=strategy,
        venue_instrument=instrument,
        trade_date=datetime.date(2026, 9, 6),
        direction=Direction.LONG,
        status=TradeStatus.PENDING_ENTRY,
        draft_context={
            "market_sentiment": "POSITIVE",
            "candles_data": [
                {"x": "2026-09-06", "y": [50000, 52000, 49000, 51000]}
            ],
        },
    )
    from tradefog.journal.models import TradeSnapshot

    TradeSnapshot.objects.create(
        trade=trade,
        planned_entry=Decimal("50000.00"),
        planned_stop=Decimal("48000.00"),
        planned_take_profit=Decimal("56000.00"),
        quantity=Decimal("0.05"),
        reward_multiple=Decimal("3.0"),
        planned_risk_percent=Decimal("1.0"),
        planned_risk_amount=Decimal("100.00"),
        planned_notional=Decimal("2500.00"),
        allocation_capital=Decimal("10000.00"),
        already_reserved_risk=Decimal(0),
        remaining_risk_capacity=Decimal("10000.00"),
        wallet_balance=Decimal("10000.00"),
        wallet_reserved=Decimal("2500.00"),
        wallet_available=Decimal("7500.00"),
        atr_value=Decimal("1500.00"),
        atr_source="bybit",
    )

    get_res = client.get(
        reverse("journal:trade_workspace", kwargs={"pk": trade.pk})
    )
    assert get_res.status_code == 200
    config = get_res.context["workspace_config"]
    assert config["is_read_only"] is True
    assert config["status"] == "pending_entry"
    assert config["checklist"]["market_sentiment"] == "POSITIVE"
    assert len(config["candles_data"]) == 1
    assert config["atr_value"] == "1500"
    assert config["atr_source"] == "bybit"

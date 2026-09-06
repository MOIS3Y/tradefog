"""Tests for trade lifecycle services, reviews, attachments, and overview."""

from __future__ import annotations

import datetime
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client
from django.urls import reverse
from pytest import mark

from tradefog.accounts.models import User
from tradefog.journal.models import (
    Asset,
    StrategyCapital,
    Trade,
    TradeAttachment,
    TradeSnapshot,
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
    AssetType,
    Direction,
    ProductKind,
    TradeStatus,
    WalletOperationKind,
)
from tradefog.journal.services import (
    cancel_trade,
    close_trade,
    open_trade,
    reserved_notional,
    set_trade_review_status,
    submit_trade,
    wallet_asset_balance,
)


def _setup_trade_lifecycle_env() -> dict[str, object]:
    """Provide a complete fixture graph for trade lifecycle testing."""
    user = User.objects.create_user(
        username="trader",
        email="trader@example.com",
        password="ValidPassword123!",
    )
    venue = Venue.objects.create(name="Bybit Test", is_active=True)
    btc = Asset.objects.create(
        symbol="BTC", name="Bitcoin", asset_type=AssetType.CRYPTO
    )
    usdt = Asset.objects.create(
        symbol="USDT", name="Tether", asset_type=AssetType.FIAT
    )
    pair = TradingPair.objects.create(
        base=btc, quote=usdt, canonical_symbol="BTC/USDT"
    )

    v_usdt = VenueWalletAsset.objects.create(
        venue=venue, asset=usdt, is_active=True
    )
    instrument = VenueInstrument.objects.create(
        venue=venue,
        pair=pair,
        exec_symbol="BTCUSDT",
        product=ProductKind.SPOT,
        price_step=Decimal("0.01"),
        qty_step=Decimal("0.001"),
        min_qty=Decimal("0.001"),
        min_notional=Decimal("5.00"),
        is_active=True,
    )

    profile = TradingProfile.objects.create(
        owner=user, venue=venue, name="Main Profile"
    )
    wallet = Wallet.objects.create(profile=profile)
    wallet_asset = WalletAsset.objects.create(
        wallet=wallet,
        venue_wallet_asset=v_usdt,
        risk_stop_capital=Decimal("500.00"),
    )
    WalletOperation.objects.create(
        wallet_asset=wallet_asset,
        kind=WalletOperationKind.DEPOSIT,
        amount=Decimal("10000.00"),
    )

    strategy = TradingStrategy.objects.create(
        profile=profile,
        name="Breakout",
        risk_percent=Decimal("1.00"),
        reward_multiple=Decimal("3.00"),
    )
    capital_alloc = StrategyCapital.objects.create(
        strategy=strategy,
        wallet_asset=wallet_asset,
        capital=Decimal("10000.00"),
    )

    trade = Trade.objects.create(
        profile=profile,
        strategy=strategy,
        venue_instrument=instrument,
        trade_date=datetime.date(2026, 9, 6),
        direction=Direction.LONG,
        status=TradeStatus.DRAFT,
    )

    return {
        "user": user,
        "profile": profile,
        "wallet_asset": wallet_asset,
        "strategy": strategy,
        "capital_alloc": capital_alloc,
        "instrument": instrument,
        "trade": trade,
    }


@mark.django_db
def test_submit_trade_creates_snapshot_and_reserves_capital() -> None:
    env = _setup_trade_lifecycle_env()
    trade = env["trade"]
    assert isinstance(trade, Trade)
    profile = env["profile"]
    assert isinstance(profile, TradingProfile)
    wallet_asset = env["wallet_asset"]
    assert isinstance(wallet_asset, WalletAsset)

    # 1% of 10000 = 100 USDT target risk
    # entry 50000, stop 48000 -> dist 2000 -> qty = 100 / 2000 = 0.05 BTC
    # notional = 50000 * 0.05 = 2500 USDT
    snapshot = submit_trade(
        trade,
        planned_entry=Decimal("50000.00"),
        planned_stop=Decimal("48000.00"),
    )

    trade.refresh_from_db()
    assert trade.status == TradeStatus.PENDING_ENTRY
    assert isinstance(snapshot, TradeSnapshot)
    assert snapshot.planned_entry == Decimal("50000.00")
    assert snapshot.planned_stop == Decimal("48000.00")
    assert snapshot.planned_take_profit == Decimal("56000.00")
    assert snapshot.quantity == Decimal("0.050")
    assert snapshot.planned_notional == Decimal("2500.00")
    assert snapshot.planned_risk_amount == Decimal("100.00")

    # Reservation derived state
    res = reserved_notional(profile, wallet_asset.venue_wallet_asset.asset_id)
    assert res == Decimal("2500.00")


@mark.django_db
def test_cannot_submit_trade_if_notional_exceeds_available_balance() -> None:
    env = _setup_trade_lifecycle_env()
    trade = env["trade"]
    assert isinstance(trade, Trade)

    # entry 50000, stop 49900 -> dist 100 -> qty = 100 / 100 = 1.000 BTC
    # notional = 50000 * 1.0 = 50000 USDT > 10000 available
    with pytest.raises(ValidationError) as exc_info:
        submit_trade(
            trade,
            planned_entry=Decimal("50000.00"),
            planned_stop=Decimal("49900.00"),
        )
    assert "exceeds available wallet funds" in str(exc_info.value)


@mark.django_db
def test_open_close_and_cancel_lifecycle() -> None:
    env = _setup_trade_lifecycle_env()
    trade = env["trade"]
    assert isinstance(trade, Trade)
    profile = env["profile"]
    assert isinstance(profile, TradingProfile)
    wallet_asset = env["wallet_asset"]
    assert isinstance(wallet_asset, WalletAsset)

    submit_trade(
        trade,
        planned_entry=Decimal("50000.00"),
        planned_stop=Decimal("48000.00"),
    )

    # Open trade
    open_trade(trade)
    trade.refresh_from_db()
    assert trade.status == TradeStatus.OPEN

    # Reservation still held
    res = reserved_notional(profile, wallet_asset.venue_wallet_asset.asset_id)
    assert res == Decimal("2500.00")

    # Close trade at target 56000.00 with 5.00 commission
    # Gross P&L = (56000 - 50000) * 0.05 = 300.00
    # Net P&L = 300.00 - 5.00 = 295.00
    close_trade(
        trade,
        actual_exit_price=Decimal("56000.00"),
        total_commission=Decimal("5.00"),
        funding_result=Decimal("0.00"),
    )
    trade.refresh_from_db()
    assert trade.status == TradeStatus.CLOSED
    assert trade.realized_pnl == Decimal("295.00")
    assert trade.actual_exit_price == Decimal("56000.00")

    # Reservation released
    res_after = reserved_notional(
        profile, wallet_asset.venue_wallet_asset.asset_id
    )
    assert res_after == Decimal("0.00")

    # Wallet balance increased by realized PnL
    bal = wallet_asset_balance(wallet_asset)
    assert bal == Decimal("10295.00")

    # Review status toggle
    set_trade_review_status(trade, completed=True)
    trade.refresh_from_db()
    assert trade.review_completed_at is not None

    set_trade_review_status(trade, completed=False)
    trade.refresh_from_db()
    assert trade.review_completed_at is None


@mark.django_db
def test_cancel_pending_trade_releases_reservation() -> None:
    env = _setup_trade_lifecycle_env()
    trade = env["trade"]
    assert isinstance(trade, Trade)
    profile = env["profile"]
    assert isinstance(profile, TradingProfile)
    wallet_asset = env["wallet_asset"]
    assert isinstance(wallet_asset, WalletAsset)

    submit_trade(
        trade,
        planned_entry=Decimal("50000.00"),
        planned_stop=Decimal("48000.00"),
    )
    assert reserved_notional(
        profile, wallet_asset.venue_wallet_asset.asset_id
    ) == Decimal("2500.00")

    cancel_trade(trade)
    trade.refresh_from_db()
    assert trade.status == TradeStatus.CANCELLED
    assert reserved_notional(
        profile, wallet_asset.venue_wallet_asset.asset_id
    ) == Decimal("0.00")


@mark.django_db
def test_trade_description_update_view(client: Client) -> None:
    env = _setup_trade_lifecycle_env()
    user = env["user"]
    assert isinstance(user, User)
    trade = env["trade"]
    assert isinstance(trade, Trade)
    client.force_login(user)

    url = reverse("journal:trade_description_update", kwargs={"pk": trade.pk})
    response = client.post(
        url,
        {"content_markdown": "## Setup Note\n\nClean daily breakout."},
    )
    assert response.status_code == 200
    assert response["X-Tradefog-Description"] == "rendered"
    assert response["X-Tradefog-Description-Empty"] == "false"
    assert "<h2>Setup Note</h2>" in response.content.decode("utf-8")

    trade.refresh_from_db()
    assert "Clean daily breakout" in trade.description_markdown


@mark.django_db
def test_trade_attachment_upload_and_delete_views(client: Client) -> None:
    env = _setup_trade_lifecycle_env()
    user = env["user"]
    assert isinstance(user, User)
    trade = env["trade"]
    assert isinstance(trade, Trade)
    client.force_login(user)

    # Valid PNG image 1x1
    png_bytes = (
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
        b"\x08\x06\x00\x00\x00\x1f\x15c4\x00\x00\x00\nIDATx\x9cc\x00\x01\x00"
        b"\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
    )
    uploaded = SimpleUploadedFile(
        "entry_chart.png", png_bytes, content_type="image/png"
    )

    upload_url = reverse(
        "journal:trade_attachment_upload", kwargs={"pk": trade.pk}
    )
    response = client.post(
        upload_url,
        {"file": uploaded},
    )
    assert response.status_code == 201
    assert "entry_chart.png" in response.content.decode("utf-8")

    att = TradeAttachment.objects.get(trade=trade)
    assert att.original_name == "entry_chart.png"

    # Serve view
    serve_url = reverse(
        "journal:trade_attachment_serve",
        kwargs={"pk": trade.pk, "attachment_pk": att.pk},
    )
    serve_res = client.get(serve_url)
    assert serve_res.status_code == 200

    # Delete view
    delete_url = reverse(
        "journal:trade_attachment_delete",
        kwargs={"pk": trade.pk, "attachment_pk": att.pk},
    )
    del_res = client.post(delete_url)
    assert del_res.status_code == 204
    assert not TradeAttachment.objects.filter(pk=att.pk).exists()


@mark.django_db
def test_trade_overview_filters_and_sorting(client: Client) -> None:
    env = _setup_trade_lifecycle_env()
    user = env["user"]
    assert isinstance(user, User)
    client.force_login(user)

    overview_url = reverse("journal:trades")
    response = client.get(overview_url)
    assert response.status_code == 200
    assert "BTC/USDT" in response.content.decode("utf-8")

    # Filter by status
    resp_draft = client.get(f"{overview_url}?status=draft")
    assert resp_draft.status_code == 200
    assert "BTC/USDT" in resp_draft.content.decode("utf-8")

    resp_closed = client.get(f"{overview_url}?status=closed")
    assert resp_closed.status_code == 200
    assert "No trades match your filters" in resp_closed.content.decode(
        "utf-8"
    )

"""Tests for asset, profile, and trading-pair workflows."""

from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.test import Client
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import override
from pytest import mark, raises

from tradefog.accounts.models import User
from tradefog.journal.models import Asset, ProfileTradingPair, TradingProfile


def create_asset(owner: User, symbol: str) -> Asset:
    """Create one owner-scoped asset used by test profiles."""
    return Asset.objects.create(owner=owner, symbol=symbol)


def create_profile(
    owner: User,
    name: str = "Primary",
    *,
    market_type: str = TradingProfile.MarketType.SPOT.value,
) -> TradingProfile:
    """Create a profile with a reusable USDT capital asset."""
    capital_asset, _created = Asset.objects.get_or_create(
        owner=owner, symbol="USDT"
    )
    return TradingProfile.objects.create(
        owner=owner,
        name=name,
        capital_asset=capital_asset,
        market_type=market_type,
        initial_capital=Decimal(10000),
        risk_stop_capital=Decimal(9000),
    )


def profile_data(profile: TradingProfile, **overrides: str) -> dict[str, str]:
    """Return a valid profile form payload using structured asset identity."""
    data = {
        "name": profile.name,
        "capital_asset": str(profile.capital_asset_id),
        "market_type": profile.market_type,
        "initial_capital": "10000",
        "risk_per_trade_percent": "1",
        "risk_stop_capital": "9000",
    }
    data.update(overrides)
    return data


def pair_data(asset: Asset) -> dict[str, str]:
    """Return valid precision data for one profile trading pair."""
    return {
        "asset": str(asset.id),
        "price_step": "0.01",
        "quantity_step": "0.00001",
        "minimum_quantity": "0.0001",
        "minimum_notional": "10",
    }


@mark.django_db
def test_assets_are_normalized_and_owner_scoped() -> None:
    """Assets should be reusable identities invisible to other owners."""
    owner = User.objects.create_user(username="owner")
    stranger = User.objects.create_user(username="stranger")
    client = Client()
    client.force_login(owner)
    response = client.post(
        "/en/assets/new/",
        {"symbol": "btc", "name": " Bitcoin ", "asset_class": "CRYPTO"},
    )
    _ = Asset.objects.create(owner=stranger, symbol="PRIVATE", name="Hidden")
    overview = client.get("/en/assets/")

    asset = Asset.objects.get(owner=owner)
    assert response.status_code == 302
    assert asset.symbol == "BTC"
    assert asset.name == "Bitcoin"
    assert b"BTC" in overview.content
    assert b"PRIVATE" not in overview.content


@mark.django_db
def test_asset_symbol_is_locked_once_referenced() -> None:
    """A structured pair must retain the asset identity it was built from."""
    user = User.objects.create_user(username="trader")
    profile = create_profile(user)
    bitcoin = create_asset(user, "BTC")
    _ = ProfileTradingPair.objects.create(
        profile=profile,
        asset=bitcoin,
        price_step=Decimal("0.01"),
        quantity_step=Decimal("0.001"),
    )
    bitcoin.symbol = "XBT"
    with raises(ValidationError):
        bitcoin.full_clean()


@mark.django_db
def test_asset_symbols_are_case_insensitively_unique_per_owner() -> None:
    """Database integrity should not depend on forms normalizing symbols."""
    user = User.objects.create_user(username="trader")
    _ = Asset.objects.create(owner=user, symbol="BTC")

    with raises(IntegrityError):
        _ = Asset.objects.create(owner=user, symbol="btc")


@mark.django_db
def test_profile_creation_uses_asset_and_market_type() -> None:
    """Profile creation should persist an explicit quote asset and market."""
    user = User.objects.create_user(username="trader")
    usdt = create_asset(user, "USDT")
    client = Client()
    client.force_login(user)
    response = client.post(
        "/en/profiles/new/",
        {
            "name": "Linear",
            "capital_asset": str(usdt.id),
            "market_type": "LINEAR_PERPETUAL",
            "initial_capital": "10000",
            "risk_per_trade_percent": "1",
            "risk_stop_capital": "9000",
        },
    )

    profile = TradingProfile.objects.get()
    assert response.status_code == 302
    assert profile.capital_asset == usdt
    assert profile.market_type == TradingProfile.MarketType.LINEAR_PERPETUAL
    assert profile.provider == TradingProfile.Provider.MANUAL


@mark.django_db
def test_profile_asset_choices_are_owner_scoped() -> None:
    """A user cannot use another owner's asset as profile capital."""
    owner = User.objects.create_user(username="owner")
    stranger = User.objects.create_user(username="stranger")
    private_asset = create_asset(stranger, "USDT")
    client = Client()
    client.force_login(owner)
    response = client.post(
        "/en/profiles/new/",
        {
            "name": "Invalid",
            "capital_asset": str(private_asset.id),
            "market_type": "SPOT",
            "initial_capital": "10000",
            "risk_per_trade_percent": "1",
            "risk_stop_capital": "9000",
        },
    )

    assert response.status_code == 200
    assert not TradingProfile.objects.exists()


@mark.django_db
def test_capital_asset_and_market_lock_after_first_pair() -> None:
    """Existing pair semantics must survive later profile corrections."""
    user = User.objects.create_user(username="trader")
    profile = create_profile(user)
    bitcoin = create_asset(user, "BTC")
    eur = create_asset(user, "EUR")
    _ = ProfileTradingPair.objects.create(
        profile=profile,
        asset=bitcoin,
        price_step=Decimal("0.01"),
        quantity_step=Decimal("0.001"),
    )
    client = Client()
    client.force_login(user)
    response = client.post(
        f"/en/profiles/{profile.id}/edit/",
        profile_data(
            profile,
            capital_asset=str(eur.id),
            market_type="LINEAR_PERPETUAL",
        ),
    )

    profile.refresh_from_db()
    assert response.status_code == 302
    assert profile.capital_asset.symbol == "USDT"
    assert profile.market_type == TradingProfile.MarketType.SPOT


@mark.django_db
def test_pair_is_structured_and_has_canonical_display_symbol() -> None:
    """Venue formatting must not be persisted in the journal identity."""
    user = User.objects.create_user(username="trader")
    profile = create_profile(user)
    bitcoin = create_asset(user, "BTC")
    client = Client()
    client.force_login(user)
    response = client.post(
        f"/en/profiles/{profile.id}/pairs/new/", pair_data(bitcoin)
    )

    trading_pair = ProfileTradingPair.objects.get()
    assert response.status_code == 302
    assert trading_pair.asset == bitcoin
    assert trading_pair.base_symbol == "BTC"
    assert trading_pair.quote_symbol == "USDT"
    assert trading_pair.symbol == "BTC/USDT"


@mark.django_db
def test_pair_assets_must_share_owner_and_differ() -> None:
    """Both structured sides of a pair must be valid identities."""
    owner = User.objects.create_user(username="owner")
    stranger = User.objects.create_user(username="stranger")
    profile = create_profile(owner)
    foreign = create_asset(stranger, "BTC")
    for asset in (profile.capital_asset, foreign):
        pair = ProfileTradingPair(
            profile=profile,
            asset=asset,
            price_step=Decimal("0.01"),
            quantity_step=Decimal("0.001"),
        )
        with raises(ValidationError):
            pair.full_clean()


@mark.django_db
def test_conflicting_archived_pair_cannot_be_restored() -> None:
    """Only one active profile pair may use a given base asset."""
    user = User.objects.create_user(username="trader")
    profile = create_profile(user)
    bitcoin = create_asset(user, "BTC")
    archived = ProfileTradingPair.objects.create(
        profile=profile,
        asset=bitcoin,
        price_step=Decimal("0.01"),
        quantity_step=Decimal("0.001"),
        archived_at=timezone.now(),
    )
    _ = ProfileTradingPair.objects.create(
        profile=profile,
        asset=bitcoin,
        price_step=Decimal("0.1"),
        quantity_step=Decimal("0.01"),
    )
    client = Client()
    client.force_login(user)
    response = client.post(
        f"/en/profiles/{profile.id}/pairs/{archived.id}/restore/",
        follow=True,
    )

    archived.refresh_from_db()
    assert archived.archived_at is not None
    assert b"active trading pair already uses this asset" in response.content


@mark.django_db
def test_foreign_profile_routes_return_not_found() -> None:
    """Every configuration route must enforce profile ownership."""
    owner = User.objects.create_user(username="owner")
    stranger = User.objects.create_user(username="stranger")
    profile = create_profile(owner)
    client = Client()
    client.force_login(stranger)
    assert client.get(f"/en/profiles/{profile.id}/").status_code == 404
    assert client.get(f"/en/profiles/{profile.id}/pairs/new/").status_code == 404


def test_journal_routes_follow_the_active_language() -> None:
    """New configuration routes should retain explicit language prefixes."""
    with override("en"):
        assert reverse("asset_overview") == "/en/assets/"
        assert reverse("trading_pair_create", args=[7]) == (
            "/en/profiles/7/pairs/new/"
        )
    with override("ru"):
        assert reverse("asset_create") == "/ru/assets/new/"
        assert reverse("trading_pair_edit", args=[7, 9]) == (
            "/ru/profiles/7/pairs/9/edit/"
        )

"""Tests for shared venues, their wallet assets, and executable instruments."""

from datetime import date
from decimal import Decimal
from pathlib import Path

from django.test import Client
from django.urls import reverse
from django.utils.translation import override
from pytest import mark

from tradefog.accounts.models import User
from tradefog.journal.forms import (
    VenueInstrumentForm,
    VenueWalletAssetForm,
)
from tradefog.journal.models import (
    Asset,
    Trade,
    TradingPair,
    TradingProfile,
    TradingStrategy,
    Venue,
    VenueInstrument,
    VenueWalletAsset,
    Wallet,
    WalletAsset,
)

PASSWORD = "correct-horse-battery-staple"


def _login_as(**user_fields: object) -> Client:
    client = Client()
    user = User.objects.create_user(
        username=user_fields.pop("username", "trader"),
        password=PASSWORD,
        **user_fields,
    )
    client.force_login(user)
    return client


def _asset(**fields: object) -> Asset:
    return Asset.objects.create(
        symbol=fields.pop("symbol", "BTC"),
        name=fields.pop("name", "Bitcoin"),
        asset_type=fields.pop("asset_type", "crypto"),
        **fields,
    )


def _pair(base: str = "BTC", quote: str = "USD", **fields: object) -> TradingPair:
    base_type = fields.pop("base_type", "crypto")
    quote_type = fields.pop("quote_type", "fiat")
    base_asset, _created = Asset.objects.get_or_create(
        symbol=base,
        defaults={"name": base, "asset_type": base_type},
    )
    quote_asset, _created = Asset.objects.get_or_create(
        symbol=quote,
        defaults={"name": quote, "asset_type": quote_type},
    )
    return TradingPair.objects.create(
        base=base_asset,
        quote=quote_asset,
        canonical_symbol=fields.pop("canonical_symbol", f"{base}/{quote}"),
        **fields,
    )


def _venue(name: str = "Bybit") -> Venue:
    return Venue.objects.create(name=name)


def _instrument(venue: Venue, pair: TradingPair, **fields: object) -> VenueInstrument:
    return VenueInstrument.objects.create(
        venue=venue,
        pair=pair,
        product=fields.pop("product", "spot"),
        exec_symbol=fields.pop("exec_symbol", f"{pair.canonical_symbol}"),
        price_step=fields.pop("price_step", Decimal("0.1")),
        qty_step=fields.pop("qty_step", Decimal("0.001")),
        **fields,
    )


def _wallet_asset(venue: Venue, asset: Asset) -> VenueWalletAsset:
    return VenueWalletAsset.objects.create(venue=venue, asset=asset)


def _journal_chain(
    user: User, venue: Venue, asset: Asset
) -> tuple[TradingProfile, Wallet, WalletAsset, TradingStrategy, VenueWalletAsset]:
    """Build a minimal owner-scoped journal so a link can be protected."""
    venue_wallet_asset = _wallet_asset(venue, asset)
    profile = TradingProfile.objects.create(
        owner=user, venue=venue, name="Main"
    )
    wallet = Wallet.objects.create(profile=profile)
    wallet_asset = WalletAsset.objects.create(
        wallet=wallet, venue_wallet_asset=venue_wallet_asset
    )
    strategy = TradingStrategy.objects.create(
        profile=profile,
        name="S1",
        settlement_wallet_asset=wallet_asset,
        strategic_capital=Decimal(1000),
        risk_percent=Decimal(1),
    )
    return profile, wallet, wallet_asset, strategy, venue_wallet_asset


def test_venue_modals_are_dialog_centered() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    catalog_root = repo_root / "src/tradefog/templates/tradefog/catalog"
    for template in (
        "partials/venue_create_modal.html",
        "partials/venue_edit_modal.html",
        "partials/venue_delete_modal.html",
        "partials/wallet_asset_add_modal.html",
        "partials/wallet_asset_remove_modal.html",
        "partials/instrument_delete_modal.html",
    ):
        source = (catalog_root / template).read_text(encoding="utf-8")
        assert "modal-dialog-centered" in source


def test_instrument_modals_are_large_and_centered() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    catalog_root = repo_root / "src/tradefog/templates/tradefog/catalog"
    for template in (
        "partials/instrument_add_modal.html",
        "partials/instrument_edit_modal.html",
    ):
        source = (catalog_root / template).read_text(encoding="utf-8")
        assert "modal-dialog-centered" in source
        assert "modal-lg" in source


@mark.django_db
def test_anonymous_user_is_redirected_to_login() -> None:
    with override("en"):
        response = Client().get(reverse("journal:venue_overview"))

    assert response.status_code == 302
    assert response.headers["Location"] == "/en/login/?next=/en/catalog/venues/"


@mark.django_db
def test_regular_user_reads_venues_without_management_actions() -> None:
    _venue(name="Bybit")
    with override("en"):
        response = _login_as().get(reverse("journal:venue_overview"))

    assert response.status_code == 200
    content = response.content.decode()
    assert "Bybit" in content
    assert "Add venue" not in content
    assert "Remove venue" not in content
    assert "Edit venue" not in content


@mark.django_db
def test_staff_user_sees_management_actions_on_cards() -> None:
    _venue(name="Bybit")
    with override("en"):
        response = _login_as(is_staff=True).get(
            reverse("journal:venue_overview")
        )

    content = response.content.decode()
    assert "Add venue" in content
    assert "Remove venue" in content
    assert "Edit venue" in content


@mark.django_db
def test_venue_cards_show_instrument_and_wallet_counts() -> None:
    venue = _venue(name="Bybit")
    pair = _pair(base="BTC", quote="USDT", base_type="crypto", quote_type="crypto")
    _instrument(venue, pair)
    _wallet_asset(venue, _asset(symbol="ETH", asset_type="crypto"))
    with override("en"):
        response = _login_as().get(reverse("journal:venue_overview"))

    content = response.content.decode()
    assert "1 instrument" in content
    assert "1 wallet asset" in content


@mark.django_db
def test_venue_empty_state_offers_create_for_staff() -> None:
    with override("en"):
        response = _login_as(is_staff=True).get(
            reverse("journal:venue_overview")
        )

    assert response.status_code == 200
    assert "No venues yet" in response.content.decode()


@mark.django_db
def test_staff_can_create_venue_with_success_alert() -> None:
    client = _login_as(is_staff=True)
    with override("en"):
        response = client.post(
            reverse("journal:venue_create"),
            {"name": "Bybit", "website": "https://www.bybit.com"},
        )

    assert response.status_code == 200
    assert Venue.objects.filter(name="Bybit").exists()
    content = response.content.decode()
    assert 'id="venue-grid"' in content
    assert 'hx-swap-oob="outerHTML"' in content
    trigger = response.headers["HX-Trigger"]
    assert "Venue added." in trigger
    assert '"kind": "success"' in trigger
    assert "venue-create-modal" in trigger


@mark.django_db
def test_duplicate_venue_name_shows_form_error() -> None:
    _venue(name="Bybit")
    client = _login_as(is_staff=True)
    with override("en"):
        response = client.post(
            reverse("journal:venue_create"), {"name": "bybit"}
        )

    assert response.status_code == 422
    assert Venue.objects.count() == 1
    assert "A venue with this name already exists." in response.content.decode()


@mark.django_db
def test_regular_user_cannot_create_venue() -> None:
    client = _login_as()
    with override("en"):
        response = client.post(
            reverse("journal:venue_create"), {"name": "Bybit"}
        )

    assert response.status_code == 403
    assert not Venue.objects.exists()


@mark.django_db
def test_staff_can_edit_venue_with_success_alert() -> None:
    venue = _venue(name="Bybit")
    client = _login_as(is_staff=True)
    with override("en"):
        response = client.post(
            reverse("journal:venue_edit", args=(venue.pk,)),
            {"name": "Bybit Pro", "website": "https://www.bybit.com"},
        )

    venue.refresh_from_db()
    assert venue.name == "Bybit Pro"
    assert response.status_code == 200
    trigger = response.headers["HX-Trigger"]
    assert "Venue updated." in trigger
    assert '"kind": "success"' in trigger


@mark.django_db
def test_regular_user_cannot_edit_venue() -> None:
    venue = _venue(name="Bybit")
    client = _login_as()
    with override("en"):
        response = client.post(
            reverse("journal:venue_edit", args=(venue.pk,)),
            {"name": "Hacked"},
        )

    assert response.status_code == 403
    venue.refresh_from_db()
    assert venue.name == "Bybit"


@mark.django_db
def test_staff_can_delete_venue_with_success_alert() -> None:
    venue = _venue(name="Bybit")
    client = _login_as(is_staff=True)
    with override("en"):
        response = client.post(
            reverse("journal:venue_delete", args=(venue.pk,))
        )

    assert response.status_code == 200
    assert not Venue.objects.filter(pk=venue.pk).exists()
    trigger = response.headers["HX-Trigger"]
    assert "Venue removed." in trigger
    assert '"kind": "success"' in trigger
    assert "venue-delete-modal" in trigger


@mark.django_db
def test_protected_venue_delete_is_blocked() -> None:
    venue = _venue(name="Bybit")
    pair = _pair()
    _instrument(venue, pair)
    client = _login_as(is_staff=True)
    with override("en"):
        response = client.post(
            reverse("journal:venue_delete", args=(venue.pk,))
        )

    assert response.status_code == 409
    assert Venue.objects.filter(pk=venue.pk).exists()
    trigger = response.headers["HX-Trigger"]
    assert "This venue is in use and cannot be removed." in trigger
    assert '"kind": "danger"' in trigger


@mark.django_db
def test_regular_user_cannot_delete_venue() -> None:
    venue = _venue(name="Bybit")
    client = _login_as()
    with override("en"):
        response = client.post(
            reverse("journal:venue_delete", args=(venue.pk,))
        )

    assert response.status_code == 403
    assert Venue.objects.filter(pk=venue.pk).exists()


@mark.django_db
def test_venue_detail_renders_identity_and_both_sections() -> None:
    venue = _venue(name="Bybit")
    pair = _pair(base="BTC", quote="USDT", base_type="crypto", quote_type="crypto")
    _instrument(venue, pair)
    _wallet_asset(venue, _asset(symbol="ETH", asset_type="crypto"))
    with override("en"):
        response = _login_as().get(reverse("journal:venue_detail", args=(venue.pk,)))

    assert response.status_code == 200
    content = response.content.decode()
    assert 'id="venue-identity"' in content
    assert 'id="wallet-asset-results"' in content
    assert 'id="instrument-results"' in content
    assert "BTC/USDT" in content
    assert "ETH" in content
    assert "Back to venues" in content


@mark.django_db
def test_regular_user_reads_detail_without_manage_actions() -> None:
    venue = _venue(name="Bybit")
    with override("en"):
        response = _login_as().get(reverse("journal:venue_detail", args=(venue.pk,)))

    content = response.content.decode()
    assert "Edit" not in content
    assert "Add wallet asset" not in content
    assert "Add instrument" not in content


@mark.django_db
def test_staff_user_sees_manage_actions_on_detail() -> None:
    venue = _venue(name="Bybit")
    with override("en"):
        response = _login_as(is_staff=True).get(
            reverse("journal:venue_detail", args=(venue.pk,))
        )

    content = response.content.decode()
    assert "Add wallet asset" in content
    assert "Add instrument" in content
    assert "Edit" in content


@mark.django_db
def test_htmx_section_request_renders_only_wallet_partial() -> None:
    venue = _venue(name="Bybit")
    _wallet_asset(venue, _asset(symbol="USDT", asset_type="crypto"))
    client = _login_as()
    with override("en"):
        response = client.get(
            reverse("journal:venue_detail", args=(venue.pk,)),
            {"section": "wallet"},
            HTTP_HX_REQUEST="true",
        )

    content = response.content.decode()
    assert 'id="wallet-asset-results"' in content
    assert 'id="instrument-results"' not in content
    assert "page-title" not in content


@mark.django_db
def test_htmx_section_request_renders_only_instrument_partial() -> None:
    venue = _venue(name="Bybit")
    _instrument(venue, _pair())
    client = _login_as()
    with override("en"):
        response = client.get(
            reverse("journal:venue_detail", args=(venue.pk,)),
            {"section": "instruments"},
            HTTP_HX_REQUEST="true",
        )

    content = response.content.decode()
    assert 'id="instrument-results"' in content
    assert 'id="wallet-asset-results"' not in content


@mark.django_db
def test_wallet_asset_form_filters_out_linked_assets() -> None:
    venue = _venue(name="Bybit")
    linked = _asset(symbol="BTC")
    free = _asset(symbol="ETH")
    _wallet_asset(venue, linked)
    form = VenueWalletAssetForm(venue=venue)

    options = [int(v) for v in form.fields["asset"].queryset.values_list("id", flat=True)]
    assert free.pk in options
    assert linked.pk not in options


@mark.django_db
def test_staff_can_add_wallet_asset_with_success_alert() -> None:
    venue = _venue(name="Bybit")
    asset = _asset(symbol="USDT", asset_type="crypto")
    client = _login_as(is_staff=True)
    with override("en"):
        response = client.post(
            reverse("journal:wallet_asset_add", args=(venue.pk,)),
            {"asset": asset.pk},
        )

    assert response.status_code == 200
    assert VenueWalletAsset.objects.filter(venue=venue, asset=asset).exists()
    trigger = response.headers["HX-Trigger"]
    assert "Wallet asset added." in trigger
    assert '"kind": "success"' in trigger
    assert "wallet-asset-add-modal" in trigger


@mark.django_db
def test_duplicate_wallet_asset_add_shows_form_error() -> None:
    venue = _venue(name="Bybit")
    asset = _asset(symbol="USDT", asset_type="crypto")
    _wallet_asset(venue, asset)
    client = _login_as(is_staff=True)
    with override("en"):
        response = client.post(
            reverse("journal:wallet_asset_add", args=(venue.pk,)),
            {"asset": asset.pk},
        )

    assert response.status_code == 422
    assert "This asset is already available on the venue." in (
        response.content.decode()
    )


@mark.django_db
def test_regular_user_cannot_add_wallet_asset() -> None:
    venue = _venue(name="Bybit")
    asset = _asset(symbol="USDT", asset_type="crypto")
    client = _login_as()
    with override("en"):
        response = client.post(
            reverse("journal:wallet_asset_add", args=(venue.pk,)),
            {"asset": asset.pk},
        )

    assert response.status_code == 403
    assert not VenueWalletAsset.objects.filter(venue=venue, asset=asset).exists()


@mark.django_db
def test_staff_can_remove_wallet_asset_with_success_alert() -> None:
    venue = _venue(name="Bybit")
    wallet_asset = _wallet_asset(
        venue, _asset(symbol="USDT", asset_type="crypto")
    )
    client = _login_as(is_staff=True)
    with override("en"):
        response = client.post(
            reverse(
                "journal:wallet_asset_remove",
                args=(venue.pk, wallet_asset.pk),
            )
        )

    assert response.status_code == 200
    assert not VenueWalletAsset.objects.filter(pk=wallet_asset.pk).exists()
    trigger = response.headers["HX-Trigger"]
    assert "Wallet asset removed." in trigger
    assert '"kind": "success"' in trigger
    assert "wallet-asset-remove-modal" in trigger


@mark.django_db
def test_protected_wallet_asset_remove_is_blocked() -> None:
    user = User.objects.create_user(username="owner", password=PASSWORD)
    venue = _venue(name="Bybit")
    asset = _asset(symbol="USDT", asset_type="crypto")
    _journal_chain(user, venue, asset)
    venue_wallet_asset = VenueWalletAsset.objects.get(venue=venue, asset=asset)
    client = _login_as(is_staff=True)
    with override("en"):
        response = client.post(
            reverse(
                "journal:wallet_asset_remove",
                args=(venue.pk, venue_wallet_asset.pk),
            )
        )

    assert response.status_code == 409
    assert VenueWalletAsset.objects.filter(pk=venue_wallet_asset.pk).exists()
    trigger = response.headers["HX-Trigger"]
    assert "This wallet asset is in use and cannot be removed." in trigger
    assert '"kind": "danger"' in trigger


@mark.django_db
def test_regular_user_cannot_remove_wallet_asset() -> None:
    venue = _venue(name="Bybit")
    wallet_asset = _wallet_asset(
        venue, _asset(symbol="USDT", asset_type="crypto")
    )
    client = _login_as()
    with override("en"):
        response = client.post(
            reverse(
                "journal:wallet_asset_remove",
                args=(venue.pk, wallet_asset.pk),
            )
        )

    assert response.status_code == 403
    assert VenueWalletAsset.objects.filter(pk=wallet_asset.pk).exists()


@mark.django_db
def test_instrument_form_clears_settlement_for_spot() -> None:
    venue = _venue(name="Bybit")
    pair = _pair()
    settlement = _asset(symbol="USDT", asset_type="crypto")
    form = VenueInstrumentForm(
        data={
            "pair": pair.pk,
            "product": "spot",
            "exec_symbol": "BTCUSD",
            "price_step": "0.1",
            "qty_step": "0.001",
            "min_qty": "",
            "min_notional": "",
            "settlement_asset": settlement.pk,
            "active": "on",
        },
        venue=venue,
    )

    assert form.is_valid()
    assert form.cleaned_data["settlement_asset"] is None


@mark.django_db
def test_instrument_form_rejects_duplicate_pair_product() -> None:
    venue = _venue(name="Bybit")
    pair = _pair()
    _instrument(venue, pair)
    form = VenueInstrumentForm(
        data={
            "pair": pair.pk,
            "product": "spot",
            "exec_symbol": "BTCPERP",
            "price_step": "0.1",
            "qty_step": "0.001",
            "settlement_asset": "",
            "active": "on",
        },
        venue=venue,
    )

    assert not form.is_valid()
    assert "This pair and product already exist on the venue." in (
        str(form.errors)
    )


@mark.django_db
def test_instrument_form_rejects_duplicate_exec_symbol() -> None:
    venue = _venue(name="Bybit")
    pair = _pair()
    _instrument(venue, pair, exec_symbol="BTCUSD")
    other = _pair(base="ETH")
    form = VenueInstrumentForm(
        data={
            "pair": other.pk,
            "product": "spot",
            "exec_symbol": "btcusd",
            "price_step": "0.1",
            "qty_step": "0.001",
            "settlement_asset": "",
            "active": "on",
        },
        venue=venue,
    )

    assert not form.is_valid()
    assert "This execution symbol already exists on the venue." in (
        str(form.errors)
    )


@mark.django_db
def test_staff_can_add_instrument_with_success_alert() -> None:
    venue = _venue(name="Bybit")
    pair = _pair()
    client = _login_as(is_staff=True)
    with override("en"):
        response = client.post(
            reverse("journal:instrument_add", args=(venue.pk,)),
            {
                "pair": pair.pk,
                "product": "spot",
                "exec_symbol": "BTCUSD",
                "price_step": "0.1",
                "qty_step": "0.001",
                "min_qty": "",
                "min_notional": "",
                "settlement_asset": "",
                "active": "on",
            },
        )

    assert response.status_code == 200
    assert VenueInstrument.objects.filter(
        venue=venue, pair=pair, exec_symbol="BTCUSD"
    ).exists()
    trigger = response.headers["HX-Trigger"]
    assert "Instrument added." in trigger
    assert '"kind": "success"' in trigger
    assert "instrument-add-modal" in trigger


@mark.django_db
def test_regular_user_cannot_add_instrument() -> None:
    venue = _venue(name="Bybit")
    pair = _pair()
    client = _login_as()
    with override("en"):
        response = client.post(
            reverse("journal:instrument_add", args=(venue.pk,)),
            {
                "pair": pair.pk,
                "product": "spot",
                "exec_symbol": "BTCUSD",
                "price_step": "0.1",
                "qty_step": "0.001",
                "settlement_asset": "",
                "active": "on",
            },
        )

    assert response.status_code == 403
    assert not VenueInstrument.objects.exists()


@mark.django_db
def test_staff_can_edit_instrument_with_success_alert() -> None:
    venue = _venue(name="Bybit")
    instrument = _instrument(venue, _pair(), exec_symbol="BTCUSD")
    client = _login_as(is_staff=True)
    with override("en"):
        response = client.post(
            reverse("journal:instrument_edit", args=(venue.pk, instrument.pk)),
            {
                "pair": instrument.pair.pk,
                "product": "spot",
                "exec_symbol": "BTCUSDT",
                "price_step": "0.1",
                "qty_step": "0.001",
                "settlement_asset": "",
                "active": "on",
            },
        )

    instrument.refresh_from_db()
    assert instrument.exec_symbol == "BTCUSDT"
    assert response.status_code == 200
    trigger = response.headers["HX-Trigger"]
    assert "Instrument updated." in trigger
    assert '"kind": "success"' in trigger
    assert "instrument-edit-modal" in trigger


@mark.django_db
def test_regular_user_cannot_edit_instrument() -> None:
    venue = _venue(name="Bybit")
    instrument = _instrument(venue, _pair(), exec_symbol="BTCUSD")
    client = _login_as()
    with override("en"):
        response = client.post(
            reverse("journal:instrument_edit", args=(venue.pk, instrument.pk)),
            {
                "pair": instrument.pair.pk,
                "product": "spot",
                "exec_symbol": "HACKED",
                "price_step": "0.1",
                "qty_step": "0.001",
                "settlement_asset": "",
                "active": "on",
            },
        )

    assert response.status_code == 403
    instrument.refresh_from_db()
    assert instrument.exec_symbol == "BTCUSD"


@mark.django_db
def test_staff_can_toggle_instrument_delisting() -> None:
    venue = _venue(name="Bybit")
    instrument = _instrument(venue, _pair(), exec_symbol="BTCUSD")
    client = _login_as(is_staff=True)
    with override("en"):
        response = client.post(
            reverse(
                "journal:instrument_toggle", args=(venue.pk, instrument.pk)
            )
        )

    instrument.refresh_from_db()
    assert instrument.active is False
    assert response.status_code == 200
    trigger = response.headers["HX-Trigger"]
    assert "Instrument delisted." in trigger
    assert '"kind": "success"' in trigger


@mark.django_db
def test_staff_can_reenable_delisted_instrument() -> None:
    venue = _venue(name="Bybit")
    instrument = _instrument(venue, _pair(), exec_symbol="BTCUSD", active=False)
    client = _login_as(is_staff=True)
    with override("en"):
        response = client.post(
            reverse(
                "journal:instrument_toggle", args=(venue.pk, instrument.pk)
            )
        )

    instrument.refresh_from_db()
    assert instrument.active is True
    trigger = response.headers["HX-Trigger"]
    assert "Instrument enabled." in trigger


@mark.django_db
def test_regular_user_cannot_toggle_instrument() -> None:
    venue = _venue(name="Bybit")
    instrument = _instrument(venue, _pair(), exec_symbol="BTCUSD")
    client = _login_as()
    with override("en"):
        response = client.post(
            reverse(
                "journal:instrument_toggle", args=(venue.pk, instrument.pk)
            )
        )

    assert response.status_code == 403
    instrument.refresh_from_db()
    assert instrument.active is True


@mark.django_db
def test_staff_can_delete_instrument_with_success_alert() -> None:
    venue = _venue(name="Bybit")
    instrument = _instrument(venue, _pair(), exec_symbol="BTCUSD")
    client = _login_as(is_staff=True)
    with override("en"):
        response = client.post(
            reverse(
                "journal:instrument_delete", args=(venue.pk, instrument.pk)
            )
        )

    assert response.status_code == 200
    assert not VenueInstrument.objects.filter(pk=instrument.pk).exists()
    trigger = response.headers["HX-Trigger"]
    assert "Instrument removed." in trigger
    assert '"kind": "success"' in trigger
    assert "instrument-delete-modal" in trigger


@mark.django_db
def test_protected_instrument_delete_is_blocked() -> None:
    user = User.objects.create_user(username="owner", password=PASSWORD)
    venue = _venue(name="Bybit")
    pair = _pair()
    asset = _asset(symbol="USDT", asset_type="crypto")
    instrument = _instrument(venue, pair, exec_symbol="BTCUSD")
    profile, _wallet, _wasset, strategy, _vwa = _journal_chain(
        user, venue, asset
    )
    Trade.objects.create(
        profile=profile,
        strategy=strategy,
        venue_instrument=instrument,
        trade_date=date(2026, 1, 1),
        direction="long",
    )
    client = _login_as(is_staff=True)
    with override("en"):
        response = client.post(
            reverse(
                "journal:instrument_delete", args=(venue.pk, instrument.pk)
            )
        )

    assert response.status_code == 409
    assert VenueInstrument.objects.filter(pk=instrument.pk).exists()
    trigger = response.headers["HX-Trigger"]
    assert "This instrument is in use and cannot be removed." in trigger
    assert '"kind": "danger"' in trigger


@mark.django_db
def test_regular_user_cannot_delete_instrument() -> None:
    venue = _venue(name="Bybit")
    instrument = _instrument(venue, _pair(), exec_symbol="BTCUSD")
    client = _login_as()
    with override("en"):
        response = client.post(
            reverse(
                "journal:instrument_delete", args=(venue.pk, instrument.pk)
            )
        )

    assert response.status_code == 403
    assert VenueInstrument.objects.filter(pk=instrument.pk).exists()


@mark.django_db
def test_venues_page_renders_in_russian() -> None:
    venue = _venue(name="Bybit")
    _instrument(venue, _pair())
    client = _login_as(is_staff=True)
    with override("ru"):
        response = client.get(reverse("journal:venue_overview"))

    assert response.status_code == 200
    content = response.content.decode()
    assert "Площадки" in content
    assert "Каталог" in content
    assert "Добавить площадку" in content


@mark.django_db
def test_venue_detail_filters_wallet_assets() -> None:
    venue = _venue(name="Bybit")
    crypto = _wallet_asset(
        venue, _asset(symbol="USDT", asset_type="crypto")
    )
    fiat = _wallet_asset(venue, _asset(symbol="USD", asset_type="fiat"))
    client = _login_as()
    with override("en"):
        response = client.get(
            reverse("journal:venue_detail", args=(venue.pk,)),
            {"section": "wallet", "wa_asset_type": "fiat"},
            HTTP_HX_REQUEST="true",
        )

    content = response.content.decode()
    assert fiat.asset.symbol in content
    assert crypto.asset.symbol not in content


@mark.django_db
def test_venue_detail_filters_instruments_by_product() -> None:
    venue = _venue(name="Bybit")
    spot = _instrument(venue, _pair(base="BTC"), exec_symbol="BTCUSD")
    perpetual = _instrument(
        venue,
        _pair(base="ETH"),
        product="perpetual_future",
        exec_symbol="ETHPERP",
    )
    client = _login_as()
    with override("en"):
        response = client.get(
            reverse("journal:venue_detail", args=(venue.pk,)),
            {"section": "instruments", "i_product": "spot"},
            HTTP_HX_REQUEST="true",
        )

    content = response.content.decode()
    assert spot.exec_symbol in content
    assert perpetual.exec_symbol not in content


@mark.django_db
def test_wallet_asset_pagination_splits_pages() -> None:
    venue = _venue(name="Bybit")
    for number in range(1, 12):
        _wallet_asset(
            venue,
            _asset(symbol=f"W{number:02d}", asset_type="crypto"),
        )
    client = _login_as()
    with override("en"):
        first = client.get(
            reverse("journal:venue_detail", args=(venue.pk,)),
            {"section": "wallet"},
        )

    first_text = first.content.decode()
    assert "Page 1 of 2" in first_text
    assert "W01" in first_text
    assert "W11" not in first_text


@mark.django_db
def test_venue_cards_render_plural_counts_in_russian() -> None:
    venue = _venue(name="Bybit")
    pair = _pair(base="BTC", quote="USDT", base_type="crypto", quote_type="crypto")
    _instrument(venue, pair)
    _wallet_asset(venue, _asset(symbol="ETH", asset_type="crypto"))
    _wallet_asset(venue, _asset(symbol="SOL", asset_type="crypto"))
    client = _login_as(is_staff=True)
    with override("ru"):
        response = client.get(reverse("journal:venue_overview"))

    assert response.status_code == 200
    content = response.content.decode()
    assert "2 актива кошелька" in content
    assert "1 инструмент" in content


@mark.django_db
def test_active_instrument_shows_open_eye_icon() -> None:
    venue = _venue(name="Bybit")
    _instrument(venue, _pair(base="BTC"), exec_symbol="BTCUSD")
    client = _login_as(is_staff=True)
    with override("en"):
        response = client.get(
            reverse("journal:venue_detail", args=(venue.pk,)),
            {"section": "instruments"},
            HTTP_HX_REQUEST="true",
        )

    content = response.content.decode()
    assert '#tabler-eye"' in content
    assert '#tabler-eye-off"' not in content


@mark.django_db
def test_delisted_instrument_shows_closed_eye_icon() -> None:
    venue = _venue(name="Bybit")
    _instrument(
        venue,
        _pair(base="BTC"),
        exec_symbol="BTCUSD",
        active=False,
    )
    client = _login_as(is_staff=True)
    with override("en"):
        response = client.get(
            reverse("journal:venue_detail", args=(venue.pk,)),
            {"section": "instruments"},
            HTTP_HX_REQUEST="true",
        )

    content = response.content.decode()
    assert '#tabler-eye-off"' in content
    assert '#tabler-eye"' not in content
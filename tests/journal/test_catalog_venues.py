import json
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any, cast

from django.forms import ModelChoiceField
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
)

PASSWORD = "correct-horse-battery-staple"


def _login_as(**user_fields: Any) -> Client:
    client = Client()
    username = user_fields.pop("username", "trader")
    user = User.objects.create_user(
        username=username,
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


def _pair(
    base: str = "BTC", quote: str = "USD", **fields: object
) -> TradingPair:
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


def _venue(name: str = "Bybit", **fields: object) -> Venue:
    return Venue.objects.create(name=name, **fields)


def _instrument(
    venue: Venue, pair: TradingPair, **fields: object
) -> VenueInstrument:
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
) -> tuple[
    TradingProfile, Wallet, WalletAsset, TradingStrategy, VenueWalletAsset
]:
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
        risk_percent=Decimal(1),
        reward_multiple=Decimal(3),
    )
    StrategyCapital.objects.create(
        strategy=strategy, wallet_asset=wallet_asset, capital=Decimal(1000)
    )
    return profile, wallet, wallet_asset, strategy, venue_wallet_asset


def test_venue_modals_are_dialog_centered() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    catalog_root = repo_root / "src/tradefog/templates/tradefog/catalog"
    for template in (
        "partials/venue_create_modal.html",
        "partials/venue_delete_modal.html",
        "partials/wallet_asset_add_modal.html",
        "partials/wallet_asset_edit_modal.html",
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
    assert (
        response.headers["Location"] == "/en/login/?next=/en/catalog/venues/"
    )


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


@mark.django_db
def test_venue_cards_show_instrument_and_wallet_counts() -> None:
    venue = _venue(name="Bybit")
    pair = _pair(
        base="BTC", quote="USDT", base_type="crypto", quote_type="crypto"
    )
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
    _pair()
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
    _pair()
    _venue(name="Bybit")
    client = _login_as(is_staff=True)
    with override("en"):
        response = client.post(
            reverse("journal:venue_create"), {"name": "bybit"}
        )

    assert response.status_code == 422
    assert Venue.objects.count() == 1
    assert (
        "A venue with this name already exists." in response.content.decode()
    )


@mark.django_db
def test_venue_create_modal_no_pairs_en() -> None:
    client = _login_as(is_staff=True)
    with override("en"):
        response = client.get(reverse("journal:venue_create"))

    assert response.status_code == 200
    content = response.content.decode()
    assert "No trading pairs available" in content
    assert "Add at least one trading pair to the catalog first" in content
    assert "Go to trading pairs" in content
    assert reverse("journal:pair_overview") in content
    assert '<input type="text" name="name"' not in content


@mark.django_db
def test_venue_create_modal_no_pairs_ru() -> None:
    client = _login_as(is_staff=True)
    with override("ru"):
        response = client.get(reverse("journal:venue_create"))
        pair_url = reverse("journal:pair_overview")

    assert response.status_code == 200
    content = response.content.decode()
    assert "Нет доступных торговых пар" in content
    assert "Сначала добавьте хотя бы одну торговую пару в каталог" in content
    assert "Перейти к торговым парам" in content
    assert pair_url in content


@mark.django_db
def test_venue_create_post_no_pairs_returns_conflict() -> None:
    client = _login_as(is_staff=True)
    with override("en"):
        response = client.post(
            reverse("journal:venue_create"),
            {"name": "Bybit"},
        )

    assert response.status_code == 409


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
    content = response.content.decode()
    assert 'id="venue-heading"' in content
    assert 'hx-swap-oob="outerHTML"' in content
    assert "Bybit Pro" in content


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
    venue = _venue(name="Bybit", is_active=False)
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
def test_active_venue_cannot_be_deleted() -> None:
    venue = _venue(name="Bybit", is_active=True)
    client = _login_as(is_staff=True)
    with override("en"):
        response = client.post(
            reverse("journal:venue_delete", args=(venue.pk,))
        )

    assert response.status_code == 409
    assert Venue.objects.filter(pk=venue.pk).exists()
    trigger = response.headers["HX-Trigger"]
    assert "Archive the venue before removing it permanently." in trigger
    assert '"kind": "danger"' in trigger
    assert "venue-delete-modal" in trigger


@mark.django_db
def test_protected_venue_delete_is_blocked() -> None:
    venue = _venue(name="Bybit", is_active=False)
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
    venue = _venue(name="Bybit", is_active=False)
    client = _login_as()
    with override("en"):
        response = client.post(
            reverse("journal:venue_delete", args=(venue.pk,))
        )

    assert response.status_code == 403
    assert Venue.objects.filter(pk=venue.pk).exists()


@mark.django_db
def test_venue_detail_renders_tabs_and_both_sections() -> None:
    venue = _venue(name="Bybit")
    pair = _pair(
        base="BTC", quote="USDT", base_type="crypto", quote_type="crypto"
    )
    _instrument(venue, pair)
    _wallet_asset(venue, _asset(symbol="ETH", asset_type="crypto"))
    with override("en"):
        response = _login_as().get(
            reverse("journal:venue_detail", args=(venue.pk,))
        )

    assert response.status_code == 200
    content = response.content.decode()
    assert 'id="venue-heading"' in content
    assert 'id="venue-instruments-tab"' in content
    assert 'id="venue-wallet-tab"' in content
    assert 'id="venue-settings-tab"' in content
    assert 'id="wallet-asset-results"' in content
    assert 'id="instrument-results"' in content
    assert "BTC/USDT" in content
    assert "ETH" in content
    assert "Back to venues" in content


@mark.django_db
def test_venue_detail_instruments_tab_is_active_by_default() -> None:
    venue = _venue(name="Bybit")
    with override("en"):
        response = _login_as().get(
            reverse("journal:venue_detail", args=(venue.pk,))
        )

    content = response.content.decode()
    assert 'class="nav-link active" href="#venue-instruments-tab"' in content
    assert 'class="tab-pane active show" id="venue-instruments-tab"' in content


@mark.django_db
def test_regular_user_reads_detail_without_manage_actions() -> None:
    venue = _venue(name="Bybit")
    with override("en"):
        response = _login_as().get(
            reverse("journal:venue_detail", args=(venue.pk,))
        )

    content = response.content.decode()
    assert "Add wallet asset" not in content
    assert "Add instrument" not in content
    assert "Save changes" not in content
    assert venue.name in content
    assert "Settings" in content


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
    assert "Save changes" in content


@mark.django_db
def test_staff_settings_tab_shows_prefilled_name_and_website_inputs() -> None:
    venue = _venue(name="Bybit")
    venue.website = "https://www.bybit.com"
    venue.save()
    with override("en"):
        response = _login_as(is_staff=True).get(
            reverse("journal:venue_detail", args=(venue.pk,))
        )

    content = response.content.decode()
    assert 'value="Bybit"' in content
    assert 'value="https://www.bybit.com"' in content
    assert "Save changes" in content


@mark.django_db
def test_regular_user_settings_tab_shows_readonly_values_only() -> None:
    venue = _venue(name="Bybit", description="Top derivatives exchange.")
    venue.website = "https://www.bybit.com"
    venue.save()
    with override("en"):
        response = _login_as().get(
            reverse("journal:venue_detail", args=(venue.pk,))
        )

    content = response.content.decode()
    assert "Bybit" in content
    assert "https://www.bybit.com" in content
    assert "Top derivatives exchange." in content
    assert "Active" in content
    assert "Save changes" not in content


@mark.django_db
def test_venue_detail_filters_collapsed_by_default() -> None:
    venue = _venue(name="Bybit")
    with override("en"):
        response = _login_as().get(
            reverse("journal:venue_detail", args=(venue.pk,))
        )

    content = response.content.decode()
    assert 'class="collapse" id="venue-instrument-filters"' in content
    assert 'class="collapse" id="venue-wallet-filters"' in content
    assert 'data-bs-target="#venue-instrument-filters"' in content


@mark.django_db
def test_venue_detail_renders_instruments_and_filters_in_russian() -> None:
    venue = _venue(name="Bybit")
    with override("ru"):
        response = _login_as().get(
            reverse("journal:venue_detail", args=(venue.pk,))
        )

    content = response.content.decode()
    assert "Инструменты" in content
    assert "Фильтры" in content


@mark.django_db
def test_venue_settings_form_renders_russian_labels() -> None:
    venue = _venue(name="Bybit")
    with override("ru"):
        response = _login_as(is_staff=True).get(
            reverse("journal:venue_edit", args=(venue.pk,))
        )

    content = response.content.decode()
    assert "Название" in content
    assert "Веб-сайт" in content


@mark.django_db
def test_instrument_form_renders_russian_labels() -> None:
    venue = _venue(name="Bybit")
    _pair(base="BTC")
    with override("ru"):
        response = _login_as(is_staff=True).get(
            reverse("journal:instrument_add", args=(venue.pk,))
        )

    content = response.content.decode()
    assert "Торговая пара" in content
    assert "Продукт" in content
    assert "Исполняемый символ" in content
    assert "Шаг цены" in content
    assert "Шаг количества" in content
    assert "Расчётный актив" in content


@mark.django_db
def test_venue_detail_filters_open_when_active() -> None:
    venue = _venue(name="Bybit")
    _instrument(venue, _pair(base="BTC"))
    _wallet_asset(venue, _asset(symbol="USDT", asset_type="crypto"))
    client = _login_as()
    with override("en"):
        response = client.get(
            reverse("journal:venue_detail", args=(venue.pk,)),
            {"section": "instruments", "i_product": "spot"},
        )

    content = response.content.decode()
    assert 'class="collapse show" id="venue-instrument-filters"' in content
    assert 'class="collapse" id="venue-wallet-filters"' in content


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
    asset_field = cast(ModelChoiceField, form.fields["asset"])
    options = [
        int(v) for v in asset_field.queryset.values_list("id", flat=True)
    ]
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
    assert not VenueWalletAsset.objects.filter(
        venue=venue, asset=asset
    ).exists()


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
    assert (
        "This wallet asset is referenced by user wallets and cannot be removed."
        in trigger
    )
    assert '"kind": "danger"' in trigger

    with override("ru"):
        ru_response = client.post(
            reverse(
                "journal:wallet_asset_remove",
                args=(venue.pk, venue_wallet_asset.pk),
            )
        )
    assert ru_response.status_code == 409
    ru_payload = json.loads(ru_response.headers["HX-Trigger"])
    assert (
        ru_payload["tradefog:toast"]["message"]
        == "Этот актив используется в кошельках пользователей и не может быть удалён. Деактивируйте его вместо удаления."
    )


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
            "is_active": "on",
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
            "is_active": "on",
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
            "is_active": "on",
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
                "is_active": "on",
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
                "is_active": "on",
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
                "is_active": "on",
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
                "is_active": "on",
            },
        )

    assert response.status_code == 403
    instrument.refresh_from_db()
    assert instrument.exec_symbol == "BTCUSD"


@mark.django_db
def test_staff_can_delist_instrument_via_edit_form() -> None:
    venue = _venue(name="Bybit")
    instrument = _instrument(venue, _pair(), exec_symbol="BTCUSD")
    client = _login_as(is_staff=True)
    with override("en"):
        response = client.post(
            reverse("journal:instrument_edit", args=(venue.pk, instrument.pk)),
            {
                "pair": instrument.pair.pk,
                "product": "spot",
                "exec_symbol": "BTCUSD",
                "price_step": "0.1",
                "qty_step": "0.001",
                "settlement_asset": "",
            },
        )

    instrument.refresh_from_db()
    assert instrument.is_active is False
    assert response.status_code == 200


@mark.django_db
def test_staff_can_reenable_instrument_via_edit_form() -> None:
    venue = _venue(name="Bybit")
    instrument = _instrument(
        venue, _pair(), exec_symbol="BTCUSD", is_active=False
    )
    client = _login_as(is_staff=True)
    with override("en"):
        response = client.post(
            reverse("journal:instrument_edit", args=(venue.pk, instrument.pk)),
            {
                "pair": instrument.pair.pk,
                "product": "spot",
                "exec_symbol": "BTCUSD",
                "price_step": "0.1",
                "qty_step": "0.001",
                "settlement_asset": "",
                "is_active": "on",
            },
        )

    instrument.refresh_from_db()
    assert instrument.is_active is True
    assert response.status_code == 200


@mark.django_db
def test_staff_cannot_delist_instrument_via_edit_form() -> None:
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
            },
        )

    assert response.status_code == 403
    instrument.refresh_from_db()
    assert instrument.is_active is True


@mark.django_db
def test_staff_can_toggle_wallet_asset_active() -> None:
    venue = _venue(name="Bybit")
    asset = _asset(symbol="USDT")
    wallet_asset = _wallet_asset(venue, asset)
    client = _login_as(is_staff=True)
    with override("en"):
        # GET form
        response = client.get(
            reverse(
                "journal:wallet_asset_edit", args=(venue.pk, wallet_asset.pk)
            )
        )
        assert response.status_code == 200
        assert "USDT" in response.content.decode()

        # POST deactivation
        response = client.post(
            reverse(
                "journal:wallet_asset_edit", args=(venue.pk, wallet_asset.pk)
            ),
            {},
        )
        assert response.status_code == 200
        wallet_asset.refresh_from_db()
        assert wallet_asset.is_active is False

        # POST re-activation
        response = client.post(
            reverse(
                "journal:wallet_asset_edit", args=(venue.pk, wallet_asset.pk)
            ),
            {"is_active": "on"},
        )
        assert response.status_code == 200
        wallet_asset.refresh_from_db()
        assert wallet_asset.is_active is True


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
    crypto = _wallet_asset(venue, _asset(symbol="USDT", asset_type="crypto"))
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
    pair = _pair(
        base="BTC", quote="USDT", base_type="crypto", quote_type="crypto"
    )
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
def test_instrument_row_shows_details_trigger_on_pair_for_all_users() -> None:
    venue = _venue(name="Bybit")
    _instrument(venue, _pair(base="BTC"), exec_symbol="BTCUSD")
    client = _login_as()
    with override("en"):
        response = client.get(
            reverse("journal:venue_detail", args=(venue.pk,)),
            {"section": "instruments"},
            HTTP_HX_REQUEST="true",
        )

    content = response.content.decode()
    assert '#tabler-eye"' not in content
    assert 'data-bs-target="#instrument-detail-modal"' in content


@mark.django_db
def test_instrument_table_has_no_delisting_switch() -> None:
    venue = _venue(name="Bybit")
    _instrument(venue, _pair(base="BTC"), exec_symbol="BTCUSD")
    client = _login_as(is_staff=True)
    with override("en"):
        response = client.get(
            reverse("journal:venue_detail", args=(venue.pk,)),
            {"section": "instruments"},
            HTTP_HX_REQUEST="true",
        )

    assert 'role="switch"' not in response.content.decode()


@mark.django_db
def test_instrument_edit_form_uses_switch_for_active_field() -> None:
    venue = _venue(name="Bybit")
    instrument = _instrument(venue, _pair(base="BTC"), exec_symbol="BTCUSD")
    client = _login_as(is_staff=True)
    with override("en"):
        response = client.get(
            reverse("journal:instrument_edit", args=(venue.pk, instrument.pk))
        )

    content = response.content.decode()
    assert 'role="switch"' in content
    assert 'name="is_active"' in content
    assert "checked" in content


@mark.django_db
def test_regular_user_can_view_instrument_details() -> None:
    venue = _venue(name="Bybit")
    instrument = _instrument(venue, _pair(base="BTC"), exec_symbol="BTCUSD")
    client = _login_as()
    with override("en"):
        response = client.get(
            reverse(
                "journal:instrument_detail", args=(venue.pk, instrument.pk)
            )
        )

    assert response.status_code == 200
    content = response.content.decode()
    assert "BTC/USD" in content
    assert "BTCUSD" in content
    assert "Price step" in content
    assert "Quantity step" in content


@mark.django_db
def test_staff_can_view_instrument_details() -> None:
    venue = _venue(name="Bybit")
    instrument = _instrument(venue, _pair(base="BTC"), exec_symbol="BTCUSD")
    client = _login_as(is_staff=True)
    with override("en"):
        response = client.get(
            reverse(
                "journal:instrument_detail", args=(venue.pk, instrument.pk)
            )
        )

    assert response.status_code == 200
    assert "Quantity step" in response.content.decode()


@mark.django_db
def test_instrument_detail_shows_explicit_or_derived_settlement() -> None:
    venue = _venue(name="Bybit")
    pair = _pair(
        base="BTC", quote="USDT", base_type="crypto", quote_type="crypto"
    )
    explicit = _instrument(
        venue, pair, product="perpetual_future", exec_symbol="BTCPERP"
    )
    explicit.settlement_asset = pair.quote
    explicit.save()
    spot = _instrument(venue, pair, exec_symbol="BTCSPOT")
    client = _login_as()
    with override("en"):
        explicit_resp = client.get(
            reverse("journal:instrument_detail", args=(venue.pk, explicit.pk))
        )
        spot_resp = client.get(
            reverse("journal:instrument_detail", args=(venue.pk, spot.pk))
        )

    assert "USDT" in explicit_resp.content.decode()
    assert "quote asset" in spot_resp.content.decode()


@mark.django_db
def test_instrument_table_shows_settlement_column() -> None:
    venue = _venue(name="Bybit")
    _instrument(venue, _pair(base="BTC"))
    client = _login_as()
    with override("en"):
        response = client.get(
            reverse("journal:venue_detail", args=(venue.pk,)),
            {"section": "instruments"},
            HTTP_HX_REQUEST="true",
        )

    content = response.content.decode()
    assert "Settlement" in content
    assert "Status" in content
    assert content.count("Settlement") == 1


@mark.django_db
def test_venue_cards_display_url_and_asset_types() -> None:
    venue = Venue.objects.create(name="Bybit", website="https://bybit.com/")
    _wallet_asset(venue, _asset(symbol="USDT", asset_type="crypto"))
    _wallet_asset(venue, _asset(symbol="USD", asset_type="fiat"))
    client = _login_as()
    with override("en"):
        response = client.get(reverse("journal:venue_overview"))

    content = response.content.decode()
    assert "bybit.com" in content
    assert "https://bybit.com/" in content
    assert "Crypto" in content
    assert "Fiat" in content


@mark.django_db
def test_instrument_table_clickable_pair_and_detail_compact_steps() -> None:
    venue = _venue(name="Bybit")
    pair = _pair(base="BTC", quote="USDT")
    inst = _instrument(
        venue,
        pair,
        price_step=Decimal("0.010000000000000000"),
        qty_step=Decimal("0.000000100000000000"),
        min_qty=Decimal("0.001000000000000000"),
        min_notional=Decimal("10.000000000000000000"),
    )
    # Regular user: no eye icon and pair text is modal trigger
    client = _login_as()
    with override("en"):
        list_resp = client.get(
            reverse("journal:venue_detail", args=(venue.pk,)),
            {"section": "instruments"},
            HTTP_HX_REQUEST="true",
        )
        detail_resp = client.get(
            reverse("journal:instrument_detail", args=(venue.pk, inst.pk))
        )

    list_content = list_resp.content.decode()
    assert "tabler-eye" not in list_content
    assert (
        f'hx-get="{reverse("journal:instrument_detail", args=(venue.pk, inst.pk))}"'
        in list_content
    )

    detail_content = detail_resp.content.decode()
    assert "0.01" in detail_content
    assert "0.010000" not in detail_content
    assert "0.0000001" in detail_content
    assert "0.000000100" not in detail_content
    assert "0.001" in detail_content
    assert "10" in detail_content


@mark.django_db
def test_venue_detail_settings_tab_alignment() -> None:
    venue = _venue(name="Bybit")
    client = _login_as(is_staff=True)
    with override("en"):
        response = client.get(
            reverse("journal:venue_detail", args=(venue.pk,))
        )

    content = response.content.decode()
    assert 'class="nav-item ms-auto"' in content
    assert 'href="#venue-settings-tab"' in content
    assert (
        "Active venues are available for creating new trading profiles."
        in content
    )
    assert 'name="is_active"' in content
    assert "checked" in content


@mark.django_db
def test_venue_description_and_archiving_in_overview() -> None:
    _active_venue = Venue.objects.create(
        name="Bybit Active",
        description="A major crypto derivatives exchange.",
        website="https://bybit.com",
        is_active=True,
    )
    _archived_venue = Venue.objects.create(
        name="FTX Closed",
        description="Defunct exchange preserved for historical records.",
        is_active=False,
    )
    client = _login_as()
    with override("en"):
        response = client.get(reverse("journal:venue_overview"))

    content = response.content.decode()
    assert "Bybit Active" in content
    assert "A major crypto derivatives exchange." in content
    assert "tf-card-description" in content
    assert "Archives" in content
    assert "1 archived venue" in content
    assert "FTX Closed" in content
    assert "Archived" in content


@mark.django_db
def test_venue_settings_edit_description_and_is_active() -> None:
    venue = Venue.objects.create(name="Binance", is_active=True)
    client = _login_as(is_staff=True)
    with override("en"):
        response = client.post(
            reverse("journal:venue_edit", args=(venue.pk,)),
            {
                "name": "Binance Global",
                "description": "Global spot and futures platform.",
                "website": "https://binance.com",
                "is_active": "false",  # unchecked in html form
            },
        )

    assert response.status_code == 200
    venue.refresh_from_db()
    assert venue.name == "Binance Global"
    assert venue.description == "Global spot and futures platform."
    assert venue.website == "https://binance.com"
    assert venue.is_active is False


@mark.django_db
def test_profile_create_only_offers_active_venues() -> None:
    _active = Venue.objects.create(name="Active Venue", is_active=True)
    _inactive = Venue.objects.create(name="Inactive Venue", is_active=False)
    client = _login_as()

    with override("en"):
        form_resp = client.get(reverse("journal:profile_create"))
        form_content = form_resp.content.decode()
        assert "Active Venue" in form_content
        assert "Inactive Venue" not in form_content


@mark.django_db
def test_venue_create_is_active_by_default() -> None:
    _pair(base="BTC", quote="USDT")
    client = _login_as(is_staff=True)

    with override("en"):
        response = client.post(
            reverse("journal:venue_create"),
            {
                "name": "OKX",
                "description": "OKX crypto exchange",
                "website": "https://okx.com",
            },
        )

    assert response.status_code == 200
    venue = Venue.objects.get(name="OKX")
    assert venue.is_active is True
    assert venue.description == "OKX crypto exchange"
    assert venue.website == "https://okx.com"
    content = response.content.decode()
    assert "OKX" in content
    assert "Archives" not in content


@mark.django_db
def test_venue_archive_action() -> None:
    venue = _venue(name="Bybit", is_active=True)
    client = _login_as(is_staff=True)

    with override("en"):
        modal_resp = client.get(
            reverse("journal:venue_archive", args=(venue.pk,))
        )
        assert modal_resp.status_code == 200
        assert "Archive the venue Bybit?" in modal_resp.content.decode()

        response = client.post(
            reverse("journal:venue_archive", args=(venue.pk,))
        )

    assert response.status_code == 200
    venue.refresh_from_db()
    assert venue.is_active is False
    trigger = response.headers["HX-Trigger"]
    assert "Venue archived." in trigger
    assert '"kind": "success"' in trigger
    assert "venue-archive-modal" in trigger


@mark.django_db
def test_venue_restore_action() -> None:
    venue = Venue.objects.create(name="Archived Venue", is_active=False)
    client = _login_as(is_staff=True)

    with override("en"):
        # Check restore button is present on overview
        overview_resp = client.get(reverse("journal:venue_overview"))
        overview_content = overview_resp.content.decode()
        assert (
            reverse("journal:venue_restore", args=(venue.pk,))
            in overview_content
        )

        # Restore venue
        restore_resp = client.post(
            reverse("journal:venue_restore", args=(venue.pk,))
        )

    assert restore_resp.status_code == 200
    venue.refresh_from_db()
    assert venue.is_active is True

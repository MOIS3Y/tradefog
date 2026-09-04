"""Tests for the shared reference catalog trading pairs collection page."""

from decimal import Decimal

from django.test import Client
from django.urls import reverse
from django.utils.translation import override
from pytest import mark

from tradefog.accounts.models import User
from tradefog.journal.forms import TradingPairForm
from tradefog.journal.models import Asset, TradingPair, Venue, VenueInstrument

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


@mark.django_db
def test_pair_form_asks_only_for_base_and_quote() -> None:
    _asset(symbol="BTC")
    _asset(symbol="USD")
    form = TradingPairForm()

    assert "base" in form.fields
    assert "quote" in form.fields
    assert "canonical_symbol" not in form.fields
    assert 'class="form-select"' in str(form)


@mark.django_db
def test_pair_form_rejects_same_base_and_quote() -> None:
    _asset(symbol="BTC")
    form = TradingPairForm(
        data={
            "base": Asset.objects.get(symbol="BTC").pk,
            "quote": Asset.objects.get(symbol="BTC").pk,
        }
    )

    assert not form.is_valid()
    assert "Base and quote must be different assets." in str(form.errors)


def test_pair_modals_are_dialog_centered() -> None:
    from pathlib import Path

    repo_root = Path(__file__).resolve().parents[2]
    catalog_root = repo_root / "src/tradefog/templates/tradefog/catalog"
    for template in (
        "partials/pair_create_modal.html",
        "partials/pair_delete_modal.html",
    ):
        source = (catalog_root / template).read_text(encoding="utf-8")
        assert "modal-dialog-centered" in source


@mark.django_db
def test_anonymous_user_is_redirected_to_login() -> None:
    with override("en"):
        response = Client().get(reverse("journal:pair_overview"))

    assert response.status_code == 302
    assert response.headers["Location"] == "/en/login/?next=/en/catalog/pairs/"


@mark.django_db
def test_regular_user_reads_catalog_without_management_actions() -> None:
    _pair(base="BTC", quote="USD")
    with override("en"):
        response = _login_as().get(reverse("journal:pair_overview"))

    assert response.status_code == 200
    content = response.content.decode()
    assert "BTC" in content
    assert "USD" in content
    assert "BTC/USD" in content
    assert "Add pair" not in content
    assert "Remove pair" not in content


@mark.django_db
def test_staff_user_sees_management_actions() -> None:
    _pair(base="BTC", quote="USD")
    with override("en"):
        response = _login_as(is_staff=True).get(
            reverse("journal:pair_overview")
        )

    content = response.content.decode()
    assert "Add pair" in content
    assert "Remove pair" in content


@mark.django_db
def test_relation_column_shows_asset_type_badges() -> None:
    _pair(base="BTC", quote="USDT", base_type="crypto", quote_type="crypto")
    with override("en"):
        response = _login_as().get(reverse("journal:pair_overview"))

    content = response.content.decode()
    assert "Relation" in content
    assert "Crypto" in content


@mark.django_db
def test_staff_can_create_pair_with_success_alert() -> None:
    _asset(symbol="BTC")
    _asset(symbol="USD")
    client = _login_as(is_staff=True)
    with override("en"):
        response = client.post(
            reverse("journal:pair_create"),
            {
                "base": Asset.objects.get(symbol="BTC").pk,
                "quote": Asset.objects.get(symbol="USD").pk,
                "canonical_symbol": "BTC/USD",
            },
        )

    assert response.status_code == 200
    assert TradingPair.objects.filter(canonical_symbol="BTC/USD").exists()
    content = response.content.decode()
    assert 'id="pair-results"' in content
    assert 'hx-swap-oob="outerHTML"' in content
    trigger = response.headers["HX-Trigger"]
    assert "Trading pair added." in trigger
    assert '"kind": "success"' in trigger
    assert "pair-create-modal" in trigger


@mark.django_db
def test_duplicate_pair_base_quote_shows_form_error() -> None:
    _pair(base="BTC", quote="USD")
    client = _login_as(is_staff=True)
    with override("en"):
        response = client.post(
            reverse("journal:pair_create"),
            {
                "base": Asset.objects.get(symbol="BTC").pk,
                "quote": Asset.objects.get(symbol="USD").pk,
            },
        )

    assert response.status_code == 422
    assert TradingPair.objects.count() == 1
    content = response.content.decode()
    assert "This trading pair already exists." in content
    assert "alert-success" not in content


@mark.django_db
def test_canonical_symbol_is_derived_from_halves() -> None:
    _asset(symbol="BTC")
    _asset(symbol="USDT")
    client = _login_as(is_staff=True)
    with override("en"):
        response = client.post(
            reverse("journal:pair_create"),
            {
                "base": Asset.objects.get(symbol="BTC").pk,
                "quote": Asset.objects.get(symbol="USDT").pk,
            },
        )

    assert response.status_code == 200
    assert TradingPair.objects.filter(
        canonical_symbol="BTC/USDT"
    ).exists()


@mark.django_db
def test_invalid_create_keeps_modal_open_with_errors() -> None:
    _asset(symbol="BTC")
    client = _login_as(is_staff=True)
    with override("en"):
        response = client.post(
            reverse("journal:pair_create"),
            {
                "base": Asset.objects.get(symbol="BTC").pk,
                "quote": "",
                "canonical_symbol": "",
            },
        )

    assert response.status_code == 422
    assert not TradingPair.objects.exists()
    assert b"invalid-feedback" in response.content


@mark.django_db
def test_regular_user_cannot_create_pair() -> None:
    _asset(symbol="BTC")
    _asset(symbol="USD")
    client = _login_as()
    with override("en"):
        response = client.post(
            reverse("journal:pair_create"),
            {
                "base": Asset.objects.get(symbol="BTC").pk,
                "quote": Asset.objects.get(symbol="USD").pk,
                "canonical_symbol": "BTC/USD",
            },
        )

    assert response.status_code == 403
    assert not TradingPair.objects.exists()


@mark.django_db
def test_search_and_pair_type_filter() -> None:
    _pair(base="BTC", quote="USDT", base_type="crypto", quote_type="crypto")
    _pair(base="EUR", quote="USD", base_type="fiat", quote_type="fiat")
    client = _login_as()

    with override("en"):
        by_search = client.get(
            reverse("journal:pair_overview"), {"q": "EUR"}
        )
        by_type = client.get(
            reverse("journal:pair_overview"), {"pair_type": "crypto/crypto"}
        )

    assert b"EUR/USD" in by_search.content
    assert b"BTC/USDT" not in by_search.content
    assert b"BTC/USDT" in by_type.content
    assert b"EUR/USD" not in by_type.content


@mark.django_db
def test_search_matches_canonical_symbol() -> None:
    _pair(base="BTC", quote="USDT", base_type="crypto", quote_type="crypto")
    _pair(base="ETH", quote="USDT", base_type="crypto", quote_type="crypto")
    client = _login_as()

    with override("en"):
        by_canonical = client.get(
            reverse("journal:pair_overview"), {"q": "BTC/USDT"}
        )

    assert b"BTC/USDT" in by_canonical.content
    assert b"ETH/USDT" not in by_canonical.content


@mark.django_db
def test_sort_links_change_column_order() -> None:
    _pair(base="BTC", quote="USD")
    _pair(base="AAPL", quote="USD", base_type="equity")
    client = _login_as()

    with override("en"):
        by_base = client.get(
            reverse("journal:pair_overview"), {"sort": "base"}
        )

    assert b"base" in by_base.content
    assert b"aria-sort" in by_base.content
    text = by_base.content.decode()
    assert text.index("AAPL") < text.index("BTC")


@mark.django_db
def test_htmx_request_renders_only_results_partial() -> None:
    _pair(base="BTC", quote="USD")
    client = _login_as()
    with override("en"):
        response = client.get(
            reverse("journal:pair_overview"),
            HTTP_HX_REQUEST="true",
        )

    content = response.content.decode()
    assert 'id="pair-results"' in content
    assert "id_pair_search" not in content
    assert "page-title" not in content


@mark.django_db
def test_staff_can_delete_pair_with_success_alert() -> None:
    pair = _pair(base="BTC", quote="USD")
    client = _login_as(is_staff=True)
    with override("en"):
        response = client.post(
            reverse("journal:pair_delete", args=(pair.pk,))
        )

    assert response.status_code == 200
    assert not TradingPair.objects.filter(pk=pair.pk).exists()
    content = response.content.decode()
    assert 'hx-swap-oob="outerHTML"' in content
    trigger = response.headers["HX-Trigger"]
    assert "Trading pair removed." in trigger
    assert '"kind": "success"' in trigger
    assert "pair-delete-modal" in trigger


@mark.django_db
def test_protected_pair_delete_is_blocked() -> None:
    pair = _pair(base="BTC", quote="USD")
    venue = Venue.objects.create(name="Bybit")
    VenueInstrument.objects.create(
        venue=venue,
        pair=pair,
        product="spot",
        exec_symbol="BTCUSD",
        price_step=Decimal("0.1"),
        qty_step=Decimal("0.001"),
    )
    client = _login_as(is_staff=True)
    with override("en"):
        response = client.post(
            reverse("journal:pair_delete", args=(pair.pk,))
        )

    assert response.status_code == 409
    assert TradingPair.objects.filter(pk=pair.pk).exists()
    trigger = response.headers["HX-Trigger"]
    assert "This trading pair is in use and cannot be removed." in trigger
    assert '"kind": "danger"' in trigger
    assert "pair-delete-modal" in trigger


@mark.django_db
def test_regular_user_cannot_delete_pair() -> None:
    pair = _pair(base="BTC", quote="USD")
    client = _login_as()
    with override("en"):
        response = client.post(
            reverse("journal:pair_delete", args=(pair.pk,))
        )

    assert response.status_code == 403
    assert TradingPair.objects.filter(pk=pair.pk).exists()


@mark.django_db
def test_pairs_page_renders_in_russian() -> None:
    _pair(base="BTC", quote="USDT", base_type="crypto", quote_type="crypto")
    client = _login_as(is_staff=True)
    with override("ru"):
        response = client.get(reverse("journal:pair_overview"))

    assert response.status_code == 200
    content = response.content.decode()
    assert "Торговые пары" in content
    assert "Каталог" in content
    assert "Добавить пару" in content
    assert "Криптовалюта" in content
    assert "Поиск" in content


@mark.django_db
def test_pagination_split_across_pages() -> None:
    for number in range(1, 12):
        _pair(base=f"PAIR{number:02d}", quote="USD")
    client = _login_as()

    with override("en"):
        first = client.get(reverse("journal:pair_overview"))
        second = client.get(
            reverse("journal:pair_overview"), {"page": "2"}
        )

    first_text = first.content.decode()
    assert "Page 1 of 2" in first_text
    assert "PAIR01" in first_text
    assert "PAIR11" not in first_text
    assert "Next page" in first_text
    assert "PAIR11" in second.content.decode()
from typing import Any

from django.test import Client
from django.urls import reverse
from django.utils.translation import override
from pytest import mark

from tradefog.accounts.models import User
from tradefog.journal.forms import AssetForm
from tradefog.journal.models import Asset, TradingPair

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


def test_asset_form_widgets_carry_tabler_classes() -> None:
    html = str(AssetForm())

    assert 'class="form-control"' in html
    assert 'class="form-select"' in html
    assert 'placeholder="BTC"' in html
    assert 'placeholder="Bitcoin"' in html


def test_asset_modals_are_dialog_centered() -> None:
    from pathlib import Path

    repo_root = Path(__file__).resolve().parents[2]
    catalog_root = repo_root / "src/tradefog/templates/tradefog/catalog"
    for template in (
        "partials/asset_create_modal.html",
        "partials/asset_delete_modal.html",
    ):
        source = (catalog_root / template).read_text(encoding="utf-8")
        assert "modal-dialog-centered" in source


@mark.django_db
def test_anonymous_user_is_redirected_to_login() -> None:
    with override("en"):
        response = Client().get(reverse("journal:asset_overview"))

    assert response.status_code == 302
    assert (
        response.headers["Location"] == "/en/login/?next=/en/catalog/assets/"
    )


@mark.django_db
def test_regular_user_reads_catalog_without_management_actions() -> None:
    _asset(symbol="BTC", name="Bitcoin")
    with override("en"):
        response = _login_as().get(reverse("journal:asset_overview"))

    assert response.status_code == 200
    content = response.content.decode()
    assert "BTC" in content
    assert "Bitcoin" in content
    assert "Add asset" not in content
    assert "Remove asset" not in content


@mark.django_db
def test_staff_user_sees_management_actions() -> None:
    _asset(symbol="BTC", name="Bitcoin")
    with override("en"):
        response = _login_as(is_staff=True).get(
            reverse("journal:asset_overview")
        )

    content = response.content.decode()
    assert "Add asset" in content
    assert "Remove asset" in content


@mark.django_db
def test_staff_can_create_asset_with_success_alert() -> None:
    client = _login_as(is_staff=True)
    with override("en"):
        response = client.post(
            reverse("journal:asset_create"),
            {
                "symbol": "ETH",
                "name": "Ethereum",
                "asset_type": "crypto",
            },
        )

    assert response.status_code == 200
    assert Asset.objects.filter(symbol="ETH").exists()
    content = response.content.decode()
    assert 'id="asset-results"' in content
    assert 'hx-swap-oob="outerHTML"' in content
    trigger = response.headers["HX-Trigger"]
    assert "Asset added." in trigger
    assert '"kind": "success"' in trigger
    assert "asset-create-modal" in trigger


@mark.django_db
def test_duplicate_asset_symbol_shows_form_error() -> None:
    _asset(symbol="BTC", name="Bitcoin")
    client = _login_as(is_staff=True)
    with override("en"):
        response = client.post(
            reverse("journal:asset_create"),
            {
                "symbol": "BTC",
                "name": "Another Bitcoin",
                "asset_type": "crypto",
            },
        )

    assert response.status_code == 422
    assert Asset.objects.filter(symbol="BTC").count() == 1
    content = response.content.decode()
    assert "An asset with this symbol already exists." in content
    assert "alert-success" not in content


@mark.django_db
def test_asset_symbol_is_normalized_and_compared_case_insensitively() -> None:
    _asset(symbol="BTC", name="Bitcoin")
    client = _login_as(is_staff=True)
    with override("en"):
        duplicate = client.post(
            reverse("journal:asset_create"),
            {
                "symbol": "btc",
                "name": "Lowercase",
                "asset_type": "crypto",
            },
        )
        fresh = client.post(
            reverse("journal:asset_create"),
            {
                "symbol": "eth",
                "name": "Ethereum",
                "asset_type": "crypto",
            },
        )

    assert duplicate.status_code == 422
    assert "An asset with this symbol already exists." in (
        duplicate.content.decode()
    )
    assert fresh.status_code == 200
    assert Asset.objects.filter(symbol="ETH").exists()


@mark.django_db
def test_invalid_create_keeps_modal_open_with_errors() -> None:
    client = _login_as(is_staff=True)
    with override("en"):
        response = client.post(
            reverse("journal:asset_create"),
            {"symbol": "", "name": "", "asset_type": "crypto"},
        )

    assert response.status_code == 422
    assert not Asset.objects.exists()
    assert b"invalid-feedback" in response.content


@mark.django_db
def test_regular_user_cannot_create_asset() -> None:
    client = _login_as()
    with override("en"):
        response = client.post(
            reverse("journal:asset_create"),
            {"symbol": "ETH", "name": "Ethereum", "asset_type": "crypto"},
        )

    assert response.status_code == 403
    assert not Asset.objects.filter(symbol="ETH").exists()


@mark.django_db
def test_search_filter_and_type_filter() -> None:
    _asset(symbol="BTC", name="Bitcoin", asset_type="crypto")
    _asset(symbol="AAPL", name="Apple", asset_type="equity")
    _asset(symbol="USD", name="US Dollar", asset_type="fiat")
    client = _login_as()

    with override("en"):
        by_name = client.get(reverse("journal:asset_overview"), {"q": "Apple"})
        by_type = client.get(
            reverse("journal:asset_overview"), {"asset_type": "fiat"}
        )

    assert b"Apple" in by_name.content
    assert b"BTC" not in by_name.content
    assert b"USD" in by_type.content
    assert b"BTC" not in by_type.content


@mark.django_db
def test_asset_filters_collapsed_by_default_and_open_when_active() -> None:
    _asset(symbol="BTC", name="Bitcoin", asset_type="crypto")
    client = _login_as()

    with override("en"):
        default = client.get(reverse("journal:asset_overview"))
        active = client.get(
            reverse("journal:asset_overview"), {"q": "Bitcoin"}
        )

    assert 'class="collapse" id="asset-filters"' in default.content.decode()
    assert (
        'class="collapse show" id="asset-filters"' in active.content.decode()
    )
    assert "Filters" in default.content.decode()


@mark.django_db
def test_sort_links_change_column_order() -> None:
    _asset(symbol="BTC", name="Zeta", asset_type="crypto")
    _asset(symbol="AAPL", name="Alpha", asset_type="equity")
    client = _login_as()

    with override("en"):
        by_symbol = client.get(
            reverse("journal:asset_overview"), {"sort": "symbol"}
        )
        by_name_desc = client.get(
            reverse("journal:asset_overview"), {"sort": "-name"}
        )

    assert b"symbol" in by_symbol.content
    assert b"aria-sort" in by_symbol.content
    symbol_text = by_symbol.content.decode()
    assert symbol_text.index("AAPL") < symbol_text.index("BTC")
    name_text = by_name_desc.content.decode()
    assert name_text.index("Zeta") < name_text.index("Alpha")


@mark.django_db
def test_htmx_request_renders_only_results_partial() -> None:
    _asset(symbol="BTC", name="Bitcoin")
    client = _login_as()
    with override("en"):
        response = client.get(
            reverse("journal:asset_overview"),
            HTTP_HX_REQUEST="true",
        )

    content = response.content.decode()
    assert 'id="asset-results"' in content
    assert "id_catalog_search" not in content
    assert "page-title" not in content


@mark.django_db
def test_staff_can_delete_asset_with_success_alert() -> None:
    asset = _asset(symbol="BTC", name="Bitcoin")
    client = _login_as(is_staff=True)
    with override("en"):
        response = client.post(
            reverse("journal:asset_delete", args=(asset.pk,))
        )

    assert response.status_code == 200
    assert not Asset.objects.filter(pk=asset.pk).exists()
    content = response.content.decode()
    assert 'hx-swap-oob="outerHTML"' in content
    trigger = response.headers["HX-Trigger"]
    assert "Asset removed." in trigger
    assert '"kind": "success"' in trigger
    assert "asset-delete-modal" in trigger


@mark.django_db
def test_protected_asset_delete_is_blocked() -> None:
    base = _asset(symbol="BTC", name="Bitcoin", asset_type="crypto")
    quote = _asset(symbol="USD", name="US Dollar", asset_type="fiat")
    _ = TradingPair.objects.create(
        base=base,
        quote=quote,
        canonical_symbol="BTC/USD",
    )
    client = _login_as(is_staff=True)
    with override("en"):
        response = client.post(
            reverse("journal:asset_delete", args=(base.pk,))
        )

    assert response.status_code == 409
    assert Asset.objects.filter(pk=base.pk).exists()
    trigger = response.headers["HX-Trigger"]
    assert "This asset is in use and cannot be removed." in trigger
    assert '"kind": "danger"' in trigger
    assert "asset-delete-modal" in trigger


@mark.django_db
def test_regular_user_cannot_delete_asset() -> None:
    asset = _asset(symbol="BTC", name="Bitcoin")
    client = _login_as()
    with override("en"):
        response = client.post(
            reverse("journal:asset_delete", args=(asset.pk,))
        )

    assert response.status_code == 403
    assert Asset.objects.filter(pk=asset.pk).exists()


@mark.django_db
def test_assets_page_renders_in_russian() -> None:
    _asset(symbol="BTC", name="Bitcoin", asset_type="crypto")
    client = _login_as(is_staff=True)
    with override("ru"):
        response = client.get(reverse("journal:asset_overview"))

    assert response.status_code == 200
    content = response.content.decode()
    assert "Активы" in content
    assert "Каталог" in content
    assert "Добавить актив" in content
    assert "Криптовалюта" in content
    assert "Поиск" in content


@mark.django_db
def test_pagination_split_across_pages() -> None:
    for number in range(1, 12):
        _asset(symbol=f"ASSET{number:02d}", asset_type="crypto")
    client = _login_as()

    with override("en"):
        first = client.get(reverse("journal:asset_overview"))
        second = client.get(reverse("journal:asset_overview"), {"page": "2"})

    first_text = first.content.decode()
    assert "Page 1 of 2" in first_text
    assert "ASSET01" in first_text
    assert "ASSET11" not in first_text
    assert "Next page" in first_text
    assert "ASSET11" in second.content.decode()

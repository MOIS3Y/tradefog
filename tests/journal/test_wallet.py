"""Tests for the owner-scoped profile wallet tab."""

import json
from decimal import Decimal
from pathlib import Path

from django.test import Client
from django.urls import reverse
from django.utils.translation import override
from pytest import mark

from tradefog.accounts.models import User
from tradefog.journal.models import (
    Asset,
    TradingProfile,
    Venue,
    VenueWalletAsset,
    Wallet,
    WalletAsset,
    WalletOperation,
)
from tradefog.journal.models.enums import WalletOperationKind

PASSWORD = "correct-horse-battery-staple"


def _owner_client(username: str = "owner") -> tuple[Client, User]:
    user = User.objects.create_user(username=username, password=PASSWORD)
    client = Client()
    client.force_login(user)
    return client, user


def _venue(name: str = "Bybit") -> Venue:
    return Venue.objects.create(name=name)


def _asset(symbol: str = "USDT") -> Asset:
    return Asset.objects.create(
        symbol=symbol, name=symbol, asset_type="crypto"
    )


def _venue_wallet_asset(
    venue: Venue, symbol: str = "USDT"
) -> VenueWalletAsset:
    return VenueWalletAsset.objects.create(venue=venue, asset=_asset(symbol))


def _profile(
    user: User, venue: Venue, name: str = "Main", **fields: object
) -> TradingProfile:
    return TradingProfile.objects.create(
        owner=user, venue=venue, name=name, **fields
    )


def _wallet(profile: TradingProfile) -> Wallet:
    return Wallet.objects.create(profile=profile)


def _wallet_asset(wallet: Wallet, venue_asset: VenueWalletAsset) -> WalletAsset:
    return WalletAsset.objects.create(
        wallet=wallet, venue_wallet_asset=venue_asset
    )


def _operation(
    wallet_asset: WalletAsset,
    kind: str = WalletOperationKind.DEPOSIT,
    amount: Decimal = Decimal(100),
) -> WalletOperation:
    return WalletOperation.objects.create(
        wallet_asset=wallet_asset,
        kind=kind,
        amount=amount,
    )


def test_wallet_modals_are_dialog_centered() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    profiles_root = repo_root / "src/tradefog/templates/tradefog/profiles"
    for template in (
        "partials/wallet_add_modal.html",
        "partials/wallet_deposit_modal.html",
        "partials/wallet_withdraw_modal.html",
        "partials/wallet_edit_modal.html",
    ):
        source = (profiles_root / template).read_text(encoding="utf-8")
        assert "modal-dialog-centered" in source


@mark.django_db
def test_wallet_tab_empty_state() -> None:
    client, owner = _owner_client()
    profile = _profile(owner, _venue())
    _wallet(profile)
    with override("en"):
        response = client.get(
            reverse("journal:profile_detail", args=(profile.pk,))
        )

    content = response.content.decode()
    assert "No wallet assets yet" in content
    assert "Add asset" in content
    assert "No operations yet" in content


@mark.django_db
def test_wallet_add_form_offers_only_venue_assets() -> None:
    client, owner = _owner_client()
    venue = _venue()
    profile = _profile(owner, venue)
    wallet = _wallet(profile)
    linked = _venue_wallet_asset(venue, "USDT")
    _venue_wallet_asset(venue, "ETH")
    _venue_wallet_asset(_venue(name="Other"), "BTC")
    _wallet_asset(wallet, linked)
    with override("en"):
        response = client.get(
            reverse("journal:wallet_add", args=(profile.pk,))
        )

    content = response.content.decode()
    assert "ETH" in content
    assert "USDT" not in content
    assert "BTC" not in content


@mark.django_db
def test_add_asset_creates_wallet_asset() -> None:
    client, owner = _owner_client()
    venue = _venue()
    profile = _profile(owner, venue)
    wallet = _wallet(profile)
    venue_asset = _venue_wallet_asset(venue, "USDT")
    with override("en"):
        response = client.post(
            reverse("journal:wallet_add", args=(profile.pk,)),
            {"venue_wallet_asset": venue_asset.pk},
        )

    assert response.status_code == 200
    assert WalletAsset.objects.filter(
        wallet=wallet, venue_wallet_asset=venue_asset
    ).exists()
    trigger = response.headers["HX-Trigger"]
    assert "Asset added to wallet." in trigger
    assert "wallet-add-modal" in trigger


@mark.django_db
def test_duplicate_wallet_asset_add_returns_422() -> None:
    client, owner = _owner_client()
    venue = _venue()
    profile = _profile(owner, venue)
    wallet = _wallet(profile)
    venue_asset = _venue_wallet_asset(venue, "USDT")
    _wallet_asset(wallet, venue_asset)
    with override("en"):
        response = client.post(
            reverse("journal:wallet_add", args=(profile.pk,)),
            {"venue_wallet_asset": venue_asset.pk},
        )

    assert response.status_code == 422
    assert "This asset is already in the wallet." in response.content.decode()


@mark.django_db
def test_deposit_records_operation_and_updates_balance() -> None:
    client, owner = _owner_client()
    venue = _venue()
    profile = _profile(owner, venue)
    wallet = _wallet(profile)
    wallet_asset = _wallet_asset(wallet, _venue_wallet_asset(venue, "USDT"))
    with override("en"):
        response = client.post(
            reverse(
                "journal:wallet_deposit",
                args=(profile.pk, wallet_asset.pk),
            ),
            {"amount": "250", "note": "initial"},
        )

    assert response.status_code == 200
    op = WalletOperation.objects.get(wallet_asset=wallet_asset)
    assert op.kind == WalletOperationKind.DEPOSIT
    assert op.amount == Decimal(250)
    assert op.note == "initial"
    trigger = response.headers["HX-Trigger"]
    assert "Deposit recorded." in trigger
    assert "wallet-deposit-modal" in trigger


@mark.django_db
def test_withdraw_reduces_balance() -> None:
    client, owner = _owner_client()
    venue = _venue()
    profile = _profile(owner, venue)
    wallet = _wallet(profile)
    wallet_asset = _wallet_asset(wallet, _venue_wallet_asset(venue, "USDT"))
    _operation(wallet_asset, amount=Decimal(300))
    with override("en"):
        response = client.post(
            reverse(
                "journal:wallet_withdraw",
                args=(profile.pk, wallet_asset.pk),
            ),
            {"amount": "100"},
        )

    assert response.status_code == 200
    op = WalletOperation.objects.get(
        wallet_asset=wallet_asset, kind=WalletOperationKind.WITHDRAWAL
    )
    assert op.amount == Decimal(100)
    assert "Withdrawal recorded." in response.headers["HX-Trigger"]
    content = response.content.decode()
    assert "200" in content


@mark.django_db
def test_withdraw_above_balance_returns_422() -> None:
    client, owner = _owner_client()
    venue = _venue()
    profile = _profile(owner, venue)
    wallet = _wallet(profile)
    wallet_asset = _wallet_asset(wallet, _venue_wallet_asset(venue, "USDT"))
    _operation(wallet_asset, amount=Decimal(100))
    with override("en"):
        response = client.post(
            reverse(
                "journal:wallet_withdraw",
                args=(profile.pk, wallet_asset.pk),
            ),
            {"amount": "200"},
        )

    assert response.status_code == 422
    assert "cannot exceed the available balance" in response.content.decode()
    assert WalletOperation.objects.count() == 1


@mark.django_db
def test_edit_floor_updates_risk_stop_capital() -> None:
    client, owner = _owner_client()
    venue = _venue()
    profile = _profile(owner, venue)
    wallet = _wallet(profile)
    wallet_asset = _wallet_asset(wallet, _venue_wallet_asset(venue, "USDT"))
    with override("en"):
        response = client.post(
            reverse(
                "journal:wallet_edit",
                args=(profile.pk, wallet_asset.pk),
            ),
            {"risk_stop_capital": "500"},
        )

    wallet_asset.refresh_from_db()
    assert wallet_asset.risk_stop_capital == Decimal(500)
    assert response.status_code == 200
    assert "Asset updated." in response.headers["HX-Trigger"]


@mark.django_db
def test_asset_card_shows_balance_and_risk_stopped_status() -> None:
    client, owner = _owner_client()
    venue = _venue()
    profile = _profile(owner, venue)
    wallet = _wallet(profile)
    wallet_asset = _wallet_asset(wallet, _venue_wallet_asset(venue, "USDT"))
    wallet_asset.risk_stop_capital = Decimal(200)
    wallet_asset.save()
    _operation(wallet_asset, amount=Decimal(100))
    with override("en"):
        response = client.get(
            reverse("journal:profile_detail", args=(profile.pk,))
        )

    content = response.content.decode()
    assert "USDT" in content
    assert "100" in content
    assert "Risk stopped" in content


@mark.django_db
def test_operations_table_paginates() -> None:
    client, owner = _owner_client()
    venue = _venue()
    profile = _profile(owner, venue)
    wallet = _wallet(profile)
    wallet_asset = _wallet_asset(wallet, _venue_wallet_asset(venue, "USDT"))
    for number in range(1, 12):
        _operation(wallet_asset, amount=Decimal(number))
    with override("en"):
        response = client.get(
            reverse("journal:profile_detail", args=(profile.pk,)),
        )

    content = response.content.decode()
    assert "Page 1 of 2" in content


@mark.django_db
def test_htmx_wallet_sort_returns_partial_only() -> None:
    client, owner = _owner_client()
    venue = _venue()
    profile = _profile(owner, venue)
    wallet = _wallet(profile)
    wallet_asset = _wallet_asset(wallet, _venue_wallet_asset(venue, "USDT"))
    _operation(wallet_asset, amount=Decimal(50))
    _operation(wallet_asset, amount=Decimal(10))
    with override("en"):
        response = client.get(
            reverse("journal:profile_detail", args=(profile.pk,)),
            {"op_sort": "amount"},
            HTTP_HX_REQUEST="true",
        )

    content = response.content.decode()
    assert 'id="profile-wallet-content"' in content
    assert "page-title" not in content


@mark.django_db
def test_archived_profile_cannot_be_mutated() -> None:
    client, owner = _owner_client()
    venue = _venue()
    profile = _profile(owner, venue, archived=True)
    wallet = _wallet(profile)
    venue_asset = _venue_wallet_asset(venue, "USDT")
    _wallet_asset(wallet, venue_asset)
    with override("en"):
        response = client.post(
            reverse("journal:wallet_add", args=(profile.pk,)),
            {"venue_wallet_asset": venue_asset.pk},
        )

    assert response.status_code == 409
    assert "Restore the profile to manage its wallet." in (
        response.headers["HX-Trigger"]
    )
    assert WalletAsset.objects.count() == 1


@mark.django_db
def test_archived_profile_wallet_is_readonly() -> None:
    client, owner = _owner_client()
    venue = _venue()
    profile = _profile(owner, venue, archived=True)
    wallet = _wallet(profile)
    _wallet_asset(wallet, _venue_wallet_asset(venue, "USDT"))
    with override("en"):
        response = client.get(
            reverse("journal:profile_detail", args=(profile.pk,))
        )

    content = response.content.decode()
    assert "USDT" in content
    assert 'data-bs-target="#wallet-add-modal"' not in content
    assert 'data-bs-target="#wallet-deposit-modal"' not in content
    assert 'data-bs-target="#wallet-withdraw-modal"' not in content


@mark.django_db
def test_wallet_actions_are_owner_scoped() -> None:
    _client, owner = _owner_client()
    venue = _venue()
    profile = _profile(owner, venue)
    wallet = _wallet(profile)
    wallet_asset = _wallet_asset(wallet, _venue_wallet_asset(venue, "USDT"))
    intruder = _login_as(username="intruder")
    with override("en"):
        deposit = intruder.post(
            reverse(
                "journal:wallet_deposit",
                args=(profile.pk, wallet_asset.pk),
            ),
            {"amount": "100"},
        )
        add = intruder.post(
            reverse("journal:wallet_add", args=(profile.pk,)),
            {"venue_wallet_asset": _venue_wallet_asset(venue, "ETH").pk},
        )

    assert deposit.status_code == 404
    assert add.status_code == 404
    assert not WalletOperation.objects.exists()


@mark.django_db
def test_wallet_tab_renders_in_russian() -> None:
    client, owner = _owner_client()
    profile = _profile(owner, _venue())
    _wallet(profile)
    with override("ru"):
        response = client.get(
            reverse("journal:profile_detail", args=(profile.pk,))
        )

    content = response.content.decode()
    assert "Активов кошелька пока нет" in content
    assert "Добавить актив" in content
    assert "Операций пока нет" in content


@mark.django_db
def test_wallet_add_toast_renders_in_russian() -> None:
    client, owner = _owner_client()
    venue = _venue()
    profile = _profile(owner, venue)
    _wallet(profile)
    venue_asset = _venue_wallet_asset(venue, "USDT")
    with override("ru"):
        response = client.post(
            reverse("journal:wallet_add", args=(profile.pk,)),
            {"venue_wallet_asset": venue_asset.pk},
        )

    assert response.status_code == 200
    trigger = json.loads(response.headers["HX-Trigger"])
    assert trigger["tradefog:toast"]["message"] == "Актив добавлен в кошелёк."


@mark.django_db
def test_edit_form_renders_for_get() -> None:
    client, owner = _owner_client()
    venue = _venue()
    profile = _profile(owner, venue)
    wallet = _wallet(profile)
    wallet_asset = _wallet_asset(wallet, _venue_wallet_asset(venue, "USDT"))
    with override("en"):
        response = client.get(
            reverse(
                "journal:wallet_edit",
                args=(profile.pk, wallet_asset.pk),
            )
        )

    assert response.status_code == 200
    content = response.content.decode()
    assert 'name="risk_stop_capital"' in content
    assert 'hx-target="#wallet-edit-body"' in content


@mark.django_db
def test_amount_renders_without_trailing_zeros() -> None:
    client, owner = _owner_client()
    venue = _venue()
    profile = _profile(owner, venue)
    wallet = _wallet(profile)
    wallet_asset = _wallet_asset(wallet, _venue_wallet_asset(venue, "USDT"))
    _operation(wallet_asset, amount=Decimal("20.000000000000000000"))
    _operation(wallet_asset, amount=Decimal("0.000100000000000000"))
    with override("en"):
        response = client.get(
            reverse("journal:profile_detail", args=(profile.pk,))
        )

    content = response.content.decode()
    assert "20.000000000000000000" not in content
    assert "20" in content
    assert "0.000100000000000000" not in content
    assert "0.0001" in content


@mark.django_db
def test_asset_card_has_note_header_and_aligned_amount() -> None:
    client, owner = _owner_client()
    venue = _venue()
    profile = _profile(owner, venue)
    wallet = _wallet(profile)
    wallet_asset = _wallet_asset(wallet, _venue_wallet_asset(venue, "USDT"))
    _operation(wallet_asset, amount=Decimal(10))
    with override("en"):
        response = client.get(
            reverse("journal:profile_detail", args=(profile.pk,))
        )

    content = response.content.decode()
    assert "<th>Note</th>" in content


def _login_as(username: str) -> Client:
    client = Client()
    user = User.objects.create_user(username=username, password=PASSWORD)
    client.force_login(user)
    return client
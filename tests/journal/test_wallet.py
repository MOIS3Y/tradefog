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
    StrategyCapital,
    Trade,
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


def _wallet_asset(
    wallet: Wallet, venue_asset: VenueWalletAsset
) -> WalletAsset:
    return WalletAsset.objects.create(
        wallet=wallet, venue_wallet_asset=venue_asset
    )


def _operation(
    wallet_asset: WalletAsset,
    kind: str = WalletOperationKind.DEPOSIT,
    amount: Decimal = Decimal(100),
    note: str = "",
) -> WalletOperation:
    return WalletOperation.objects.create(
        wallet_asset=wallet_asset,
        kind=kind,
        amount=amount,
        note=note,
    )


def _reserve_trade(
    profile: TradingProfile,
    strategy: TradingStrategy,
    wallet_asset: WalletAsset,
    notional: Decimal,
) -> Trade:
    """Create a pending-entry trade reserving the asset's wallet capital."""
    venue = profile.venue
    pair = TradingPair.objects.create(
        base=Asset.objects.create(symbol="BTC", asset_type="crypto"),
        quote=wallet_asset.venue_wallet_asset.asset,
        canonical_symbol="BTC/USDT",
    )
    instrument = VenueInstrument.objects.create(
        venue=venue,
        pair=pair,
        product="spot",
        exec_symbol="BTCUSDT",
        price_step=Decimal("0.1"),
        qty_step=Decimal("0.001"),
    )
    trade = Trade.objects.create(
        profile=profile,
        strategy=strategy,
        venue_instrument=instrument,
        trade_date="2026-01-01",
        direction="long",
        status="pending_entry",
    )
    TradeSnapshot.objects.create(
        trade=trade,
        planned_entry=Decimal(100),
        planned_stop=Decimal(90),
        reward_multiple=Decimal(3),
        planned_risk_percent=Decimal(1),
        planned_risk_amount=Decimal(10),
        planned_notional=notional,
        allocation_capital=Decimal(1000),
        already_reserved_risk=Decimal(0),
        remaining_risk_capacity=Decimal(10),
        wallet_balance=Decimal(1000),
        wallet_reserved=Decimal(0),
        wallet_available=Decimal(1000),
    )
    return trade


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
    assert ">ETH</option>" in content
    assert "Bybit / ETH" not in content
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
def test_wallet_add_shows_empty_state_when_all_assets_are_linked() -> None:
    client, owner = _owner_client()
    venue = _venue()
    profile = _profile(owner, venue)
    wallet = _wallet(profile)
    venue_asset = _venue_wallet_asset(venue, "USDT")
    _wallet_asset(wallet, venue_asset)
    with override("en"):
        response = client.get(
            reverse("journal:wallet_add", args=(profile.pk,)),
        )

    content = response.content.decode()
    assert "All venue assets are already added" in content
    assert "Add asset" not in content


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
def test_asset_card_shows_balance_and_below_floor_status() -> None:
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
    assert "Below floor" in content


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
    profile = _profile(owner, venue, is_archived=True)
    wallet = _wallet(profile)
    venue_asset = _venue_wallet_asset(venue, "USDT")
    _wallet_asset(wallet, venue_asset)
    with override("en"):
        response = client.post(
            reverse("journal:wallet_add", args=(profile.pk,)),
            {"venue_wallet_asset": venue_asset.pk},
        )

    assert response.status_code == 409
    assert (
        "Restore the profile to manage its wallet."
        in (response.headers["HX-Trigger"])
    )
    assert WalletAsset.objects.count() == 1


@mark.django_db
def test_archived_profile_wallet_is_readonly() -> None:
    client, owner = _owner_client()
    venue = _venue()
    profile = _profile(owner, venue, is_archived=True)
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


@mark.django_db
def test_reservation_reduces_available_balance() -> None:
    client, owner = _owner_client()
    venue = _venue()
    profile = _profile(owner, venue)
    wallet = _wallet(profile)
    wallet_asset = _wallet_asset(wallet, _venue_wallet_asset(venue, "USDT"))
    _operation(wallet_asset, amount=Decimal(1000))
    strategy = TradingStrategy.objects.create(
        profile=profile,
        name="S",
        risk_percent=Decimal(1),
        reward_multiple=Decimal(3),
    )
    _reserve_trade(profile, strategy, wallet_asset, Decimal(400))
    with override("en"):
        response = client.get(
            reverse("journal:profile_detail", args=(profile.pk,))
        )

    content = response.content.decode()
    assert "600" in content
    assert "400" in content


@mark.django_db
def test_withdrawal_respects_reservation() -> None:
    client, owner = _owner_client()
    venue = _venue()
    profile = _profile(owner, venue)
    wallet = _wallet(profile)
    wallet_asset = _wallet_asset(wallet, _venue_wallet_asset(venue, "USDT"))
    _operation(wallet_asset, amount=Decimal(1000))
    strategy = TradingStrategy.objects.create(
        profile=profile,
        name="S",
        risk_percent=Decimal(1),
        reward_multiple=Decimal(3),
    )
    _reserve_trade(profile, strategy, wallet_asset, Decimal(400))
    with override("en"):
        over = client.post(
            reverse(
                "journal:wallet_withdraw",
                args=(profile.pk, wallet_asset.pk),
            ),
            {"amount": "700"},
        )
        allowed = client.post(
            reverse(
                "journal:wallet_withdraw",
                args=(profile.pk, wallet_asset.pk),
            ),
            {"amount": "500"},
        )

    assert over.status_code == 422
    assert allowed.status_code == 200


@mark.django_db
def test_wallet_remove_hard_deletes_when_unreferenced_and_zero_balance() -> (
    None
):
    client, owner = _owner_client()
    venue = _venue()
    profile = _profile(owner, venue)
    wallet = _wallet(profile)
    wallet_asset = _wallet_asset(wallet, _venue_wallet_asset(venue, "USDT"))
    with override("en"):
        # GET confirm modal
        confirm = client.get(
            reverse(
                "journal:wallet_remove", args=(profile.pk, wallet_asset.pk)
            )
        )
        assert confirm.status_code == 200
        assert "Remove" in confirm.content.decode()

        # POST remove
        response = client.post(
            reverse(
                "journal:wallet_remove", args=(profile.pk, wallet_asset.pk)
            )
        )
    assert response.status_code == 200
    assert not WalletAsset.objects.filter(pk=wallet_asset.pk).exists()
    assert "Asset removed from wallet." in response.headers["HX-Trigger"]


@mark.django_db
def test_wallet_remove_refuses_when_balance_positive() -> None:
    client, owner = _owner_client()
    venue = _venue()
    profile = _profile(owner, venue)
    wallet = _wallet(profile)
    wallet_asset = _wallet_asset(wallet, _venue_wallet_asset(venue, "USDT"))
    _operation(wallet_asset, amount=Decimal(100))
    with override("en"):
        response = client.post(
            reverse(
                "journal:wallet_remove", args=(profile.pk, wallet_asset.pk)
            )
        )
    assert response.status_code == 409
    assert WalletAsset.objects.filter(pk=wallet_asset.pk).exists()
    assert "Withdraw or convert all funds" in response.headers["HX-Trigger"]


@mark.django_db
def test_wallet_remove_archives_when_referenced() -> None:
    client, owner = _owner_client()
    venue = _venue()
    profile = _profile(owner, venue)
    wallet = _wallet(profile)
    wallet_asset = _wallet_asset(wallet, _venue_wallet_asset(venue, "USDT"))
    strategy = TradingStrategy.objects.create(
        profile=profile,
        name="S",
        risk_percent=Decimal(1),
        reward_multiple=Decimal(3),
    )
    # create archived strategy capital
    StrategyCapital.objects.create(
        strategy=strategy,
        wallet_asset=wallet_asset,
        capital=Decimal(100),
        is_archived=True,
    )
    with override("en"):
        response = client.post(
            reverse(
                "journal:wallet_remove", args=(profile.pk, wallet_asset.pk)
            )
        )
    assert response.status_code == 200
    wallet_asset.refresh_from_db()
    assert wallet_asset.is_archived is True
    assert "Asset archived." in response.headers["HX-Trigger"]


@mark.django_db
def test_wallet_restore_and_delisted_refusal() -> None:
    client, owner = _owner_client()
    venue = _venue()
    profile = _profile(owner, venue)
    wallet = _wallet(profile)
    venue_asset = _venue_wallet_asset(venue, "USDT")
    wallet_asset = _wallet_asset(wallet, venue_asset)
    wallet_asset.is_archived = True
    wallet_asset.save()

    # When venue asset is active, restore succeeds
    with override("en"):
        response = client.post(
            reverse(
                "journal:wallet_restore", args=(profile.pk, wallet_asset.pk)
            )
        )
    assert response.status_code == 200
    wallet_asset.refresh_from_db()
    assert wallet_asset.is_archived is False
    assert "Asset restored." in response.headers["HX-Trigger"]

    # When venue asset is delisted, restore is refused
    wallet_asset.is_archived = True
    wallet_asset.save()
    venue_asset.is_active = False
    venue_asset.save()

    with override("en"):
        response = client.post(
            reverse(
                "journal:wallet_restore", args=(profile.pk, wallet_asset.pk)
            )
        )
    assert response.status_code == 409
    wallet_asset.refresh_from_db()
    assert wallet_asset.is_archived is True
    assert "delisted" in response.headers["HX-Trigger"]


@mark.django_db
def test_wallet_add_modal_when_venue_has_no_wallet_assets() -> None:
    # 1. Staff user
    staff_client = Client()
    staff_user = User.objects.create_user(
        username="admin", password=PASSWORD, is_staff=True
    )
    staff_client.force_login(staff_user)
    venue = _venue("EmptyVenue")
    profile = _profile(staff_user, venue)
    _ = _wallet(profile)

    with override("en"):
        response = staff_client.get(
            reverse("journal:wallet_add", args=(profile.pk,))
        )
    assert response.status_code == 200
    content = response.content.decode()
    assert "No assets available on venue" in content
    assert (
        "This venue does not have any wallet assets configured yet. Add wallet assets to the venue in the catalog first."
        in content
    )
    assert reverse("journal:venue_detail", args=(venue.pk,)) in content

    # 2. Regular user
    client, owner = _owner_client()
    user_profile = _profile(owner, venue)
    _ = _wallet(user_profile)

    with override("en"):
        response = client.get(
            reverse("journal:wallet_add", args=(user_profile.pk,))
        )
    assert response.status_code == 200
    content = response.content.decode()
    assert "No assets available on venue" in content
    assert (
        "This venue does not have any wallet assets configured yet. Ask a staff member to add wallet assets to the venue."
        in content
    )
    assert reverse("journal:venue_detail", args=(venue.pk,)) not in content

    # 3. Russian translation
    with override("ru"):
        response = staff_client.get(
            reverse("journal:wallet_add", args=(profile.pk,))
        )
    assert response.status_code == 200
    content = response.content.decode()
    assert "На площадке нет доступных активов" in content
    assert (
        "Для этой площадки ещё не настроены активы кошелька. Сначала добавьте активы кошелька для площадки в каталог."
        in content
    )
    assert "Перейти к площадке" in content

    # 4. POST is rejected with 409
    with override("en"):
        post_resp = client.post(
            reverse("journal:wallet_add", args=(user_profile.pk,)),
            {"venue_wallet_asset": 1},
        )
    assert post_resp.status_code == 409


@mark.django_db
def test_wallet_remove_balance_error_translation_ru() -> None:
    client, owner = _owner_client()
    venue = _venue()
    profile = _profile(owner, venue)
    wallet = _wallet(profile)
    wallet_asset = _wallet_asset(wallet, _venue_wallet_asset(venue, "USDT"))
    _operation(wallet_asset, amount=Decimal(100))

    with override("ru"):
        response = client.post(
            reverse(
                "journal:wallet_remove", args=(profile.pk, wallet_asset.pk)
            )
        )
    assert response.status_code == 409
    payload = json.loads(response.headers["HX-Trigger"])
    assert (
        payload["tradefog:toast"]["message"]
        == "Выведите или конвертируйте все средства, чтобы баланс стал нулевым, перед архивированием этого актива."
    )


@mark.django_db
def test_wallet_archived_section_header_format_and_translation() -> None:
    client, owner = _owner_client()
    venue = _venue()
    profile = _profile(owner, venue)
    wallet = _wallet(profile)
    wallet_asset = _wallet_asset(wallet, _venue_wallet_asset(venue, "USDT"))
    wallet_asset.is_archived = True
    wallet_asset.save()

    with override("ru"):
        response = client.get(
            reverse("journal:profile_detail", args=(profile.pk,)),
            {"tab": "wallet"},
        )
    assert response.status_code == 200
    content = response.content.decode()
    assert "Архив" in content
    assert "1 архивный актив" in content
    assert "h4 mb-0" in content


@mark.django_db
def test_wallet_deposit_refused_when_delisted() -> None:
    client, owner = _owner_client()
    venue = _venue()
    profile = _profile(owner, venue)
    wallet = _wallet(profile)
    venue_asset = _venue_wallet_asset(venue, "USDT")
    wallet_asset = _wallet_asset(wallet, venue_asset)

    # Delist the venue asset
    venue_asset.is_active = False
    venue_asset.save()

    # Asset card does not show deposit button when delisted
    resp_tab = client.get(
        reverse("journal:profile_detail", args=(profile.pk,)),
        {"tab": "wallet"},
    )
    assert resp_tab.status_code == 200
    card_content = resp_tab.content.decode()
    assert "Delisted" in card_content
    assert (
        f'hx-get="{reverse("journal:wallet_deposit", args=(profile.pk, wallet_asset.pk))}"'
        not in card_content
    )

    # Deposit view refuses with 409 and toast
    with override("ru"):
        post_resp = client.post(
            reverse(
                "journal:wallet_deposit", args=(profile.pk, wallet_asset.pk)
            ),
            {"amount": 100},
        )
    assert post_resp.status_code == 409
    payload = json.loads(post_resp.headers["HX-Trigger"])
    assert (
        payload["tradefog:toast"]["message"]
        == "Пополнение недоступно для активов, исключённых из листинга площадки."
    )


@mark.django_db
def test_wallet_operation_edit_note_get_and_post() -> None:
    client, owner = _owner_client()
    venue = _venue()
    profile = _profile(owner, venue)
    wallet = _wallet(profile)
    wallet_asset = _wallet_asset(wallet, _venue_wallet_asset(venue, "USDT"))
    op = _operation(wallet_asset, amount=Decimal(500), note="Initial note")

    with override("en"):
        # GET form fragment
        get_resp = client.get(
            reverse("journal:wallet_operation_edit", args=(profile.pk, op.pk))
        )
        assert get_resp.status_code == 200
        get_content = get_resp.content.decode()
        assert 'value="Initial note"' in get_content
        assert 'name="note"' in get_content

        # POST update note
        post_resp = client.post(
            reverse("journal:wallet_operation_edit", args=(profile.pk, op.pk)),
            {"note": "Updated note for deposit"},
        )

    assert post_resp.status_code == 200
    op.refresh_from_db()
    assert op.note == "Updated note for deposit"
    post_content = post_resp.content.decode()
    assert "Updated note for deposit" in post_content
    assert 'id="profile-wallet-content"' in post_content
    assert 'hx-swap-oob="outerHTML"' in post_content

    trigger = post_resp.headers["HX-Trigger"]
    assert "Operation note updated." in trigger
    assert '"id": "wallet-operation-edit-modal"' in trigger


@mark.django_db
def test_wallet_operation_edit_refused_on_archived_profile() -> None:
    client, owner = _owner_client()
    venue = _venue()
    profile = _profile(owner, venue, is_archived=True)
    wallet = _wallet(profile)
    wallet_asset = _wallet_asset(wallet, _venue_wallet_asset(venue, "USDT"))
    op = _operation(wallet_asset, amount=Decimal(100), note="Old")

    with override("en"):
        response = client.post(
            reverse("journal:wallet_operation_edit", args=(profile.pk, op.pk)),
            {"note": "New"},
        )

    assert response.status_code == 409
    op.refresh_from_db()
    assert op.note == "Old"
    trigger = response.headers["HX-Trigger"]
    assert "Restore the profile" in trigger


@mark.django_db
def test_wallet_operation_edit_cannot_be_accessed_by_other_user() -> None:
    _client1, user1 = _owner_client(username="user1")
    client2, _user2 = _owner_client(username="user2")
    venue = _venue()
    profile1 = _profile(user1, venue)
    wallet1 = _wallet(profile1)
    wallet_asset1 = _wallet_asset(wallet1, _venue_wallet_asset(venue, "USDT"))
    op1 = _operation(wallet_asset1, amount=Decimal(100), note="User1 Note")

    with override("en"):
        response = client2.post(
            reverse(
                "journal:wallet_operation_edit", args=(profile1.pk, op1.pk)
            ),
            {"note": "Hacked"},
        )

    assert response.status_code == 404
    op1.refresh_from_db()
    assert op1.note == "User1 Note"

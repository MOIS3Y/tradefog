"""Tests for the owner-scoped profile strategies tab."""

import json
from decimal import Decimal
from pathlib import Path

from django.test import Client
from django.urls import reverse
from django.utils.translation import override
from pytest import mark

from tradefog.accounts.models import User
from tradefog.journal.forms import StrategyCapitalForm
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


def _owner_client(username: str = "owner") -> tuple[Client, User]:
    user = User.objects.create_user(username=username, password=PASSWORD)
    client = Client()
    client.force_login(user)
    return client, user


@mark.django_db
def test_strategy_plan_values_are_compact_formatted() -> None:
    client, _owner, profile, _wallet, _eligible = _journal_chain()
    _strategy(profile, name="S1", risk_percent=Decimal("1.000000"))
    with override("en"):
        response = client.get(
            reverse("journal:profile_detail", args=(profile.pk,))
        )

    content = response.content.decode()
    assert "1.000000" not in content
    assert ">1%<" in content or "1%" in content


def _login_as(username: str) -> Client:
    client = Client()
    user = User.objects.create_user(username=username, password=PASSWORD)
    client.force_login(user)
    return client


def _submitted_trade(strategy: TradingStrategy, status: str = "closed") -> Trade:
    """Create a trade against the strategy's venue instrument."""
    profile = strategy.profile
    instrument = profile.venue.instruments.first()
    return Trade.objects.create(
        profile=profile,
        strategy=strategy,
        venue_instrument=instrument,
        trade_date="2026-01-01",
        direction="long",
        status=status,
    )


@mark.django_db
def test_strategy_plan_fields_are_locked_after_creation() -> None:
    client, _owner, profile, _wallet, _eligible = _journal_chain()
    strategy = _strategy(profile, risk_percent=Decimal(1))
    with override("en"):
        response = client.post(
            reverse("journal:strategy_edit", args=(profile.pk, strategy.pk)),
            {"name": "Renamed", "risk_percent": "9", "reward_multiple": "9"},
        )

    strategy.refresh_from_db()
    assert strategy.name == "Renamed"
    assert strategy.risk_percent == Decimal(1)
    assert strategy.reward_multiple == Decimal(3)
    assert response.status_code == 200


@mark.django_db
def test_strategy_plan_fields_are_locked_after_creation_with_trades() -> None:
    client, _owner, profile, _wallet, _eligible = _journal_chain()
    strategy = _strategy(profile, risk_percent=Decimal(1))
    _submitted_trade(strategy)
    with override("en"):
        response = client.post(
            reverse("journal:strategy_edit", args=(profile.pk, strategy.pk)),
            {"name": "Renamed", "risk_percent": "9", "reward_multiple": "9"},
        )

    strategy.refresh_from_db()
    assert strategy.name == "Renamed"
    assert strategy.risk_percent == Decimal(1)
    assert strategy.reward_multiple == Decimal(3)
    assert response.status_code == 200


@mark.django_db
def test_strategy_edit_form_disables_plan_fields() -> None:
    client, _owner, profile, _wallet, _eligible = _journal_chain()
    strategy = _strategy(profile)
    with override("en"):
        response = client.get(
            reverse("journal:strategy_edit", args=(profile.pk, strategy.pk))
        )

    content = response.content.decode()
    assert 'name="risk_percent"' in content
    assert 'name="reward_multiple"' in content
    assert content.count("disabled") >= 2
    assert "Locked after the strategy is created." in content


@mark.django_db
def test_strategy_edit_form_renders_compact_values() -> None:
    client, _owner, profile, _wallet, _eligible = _journal_chain()
    strategy = _strategy(profile, risk_percent=Decimal("1.000000"))
    with override("en"):
        response = client.get(
            reverse("journal:strategy_edit", args=(profile.pk, strategy.pk))
        )

    content = response.content.decode()
    assert 'value="1.000000"' not in content
    assert 'name="risk_percent"' in content
    assert 'value="1"' in content


@mark.django_db
def test_locked_strategy_allows_allocations() -> None:
    client, _owner, profile, _wallet, eligible = _journal_chain()
    strategy = _strategy(profile)
    _submitted_trade(strategy)
    with override("en"):
        response = client.post(
            reverse("journal:strategy_capital_add", args=(profile.pk, strategy.pk)),
            {"wallet_asset": eligible.pk, "capital": "1000"},
        )

    assert response.status_code == 200
    assert StrategyCapital.objects.filter(strategy=strategy).count() == 1


def _asset(symbol: str) -> Asset:
    return Asset.objects.create(symbol=symbol, name=symbol, asset_type="crypto")


def _pair(base: str, quote: str) -> TradingPair:
    return TradingPair.objects.create(
        base=_asset(base), quote=_asset(quote), canonical_symbol=f"{base}/{quote}"
    )


def _venue(name: str = "Bybit") -> Venue:
    return Venue.objects.create(name=name)


def _instrument(venue: Venue, pair: TradingPair, product: str = "spot") -> VenueInstrument:
    return VenueInstrument.objects.create(
        venue=venue,
        pair=pair,
        product=product,
        exec_symbol=f"{pair.canonical_symbol}-{product}",
        price_step=Decimal("0.1"),
        qty_step=Decimal("0.001"),
    )


def _venue_wallet_asset(venue: Venue, asset: Asset) -> VenueWalletAsset:
    return VenueWalletAsset.objects.create(venue=venue, asset=asset)


def _profile(user: User, venue: Venue, **fields: object) -> TradingProfile:
    return TradingProfile.objects.create(
        owner=user, venue=venue, name="Main", **fields
    )


def _wallet(profile: TradingProfile) -> Wallet:
    return Wallet.objects.create(profile=profile)


def _wallet_asset(wallet: Wallet, venue_asset: VenueWalletAsset) -> WalletAsset:
    return WalletAsset.objects.create(
        wallet=wallet, venue_wallet_asset=venue_asset
    )


def _strategy(
    profile: TradingProfile, name: str = "Breakout", **fields: object
) -> TradingStrategy:
    return TradingStrategy.objects.create(
        profile=profile,
        name=name,
        risk_percent=fields.pop("risk_percent", Decimal(1)),
        reward_multiple=fields.pop("reward_multiple", Decimal(3)),
        **fields,
    )


def _journal_chain() -> tuple[Client, User, TradingProfile, Wallet, WalletAsset]:
    """Build a venue, an instrument, a wallet, and an eligible wallet asset."""
    client, owner = _owner_client()
    venue = _venue()
    pair = _pair("BTC", "USDT")
    _instrument(venue, pair)
    quote = pair.quote
    profile = _profile(owner, venue)
    wallet = _wallet(profile)
    eligible = _wallet_asset(wallet, _venue_wallet_asset(venue, quote))
    return client, owner, profile, wallet, eligible


def test_strategy_modals_are_dialog_centered() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    profiles_root = repo_root / "src/tradefog/templates/tradefog/profiles"
    for template in (
        "partials/strategy_create_modal.html",
        "partials/strategy_edit_modal.html",
        "partials/strategy_archive_modal.html",
        "partials/strategy_detail_modal.html",
    ):
        source = (profiles_root / template).read_text(encoding="utf-8")
        assert "modal-dialog-centered" in source


@mark.django_db
def test_strategies_tab_empty_state() -> None:
    client, owner = _owner_client()
    profile = _profile(owner, _venue())
    with override("en"):
        response = client.get(
            reverse("journal:profile_detail", args=(profile.pk,))
        )

    content = response.content.decode()
    assert "No strategies yet" in content
    assert "Add strategy" in content


@mark.django_db
def test_create_strategy_with_success_toast() -> None:
    client, _owner, profile, _wallet, _eligible = _journal_chain()
    with override("en"):
        response = client.post(
            reverse("journal:strategy_create", args=(profile.pk,)),
            {
                "name": "Breakout",
                "description": "",
                "risk_percent": "1.5",
                "reward_multiple": "3",
            },
        )

    assert response.status_code == 200
    strategy = TradingStrategy.objects.get(profile=profile, name="Breakout")
    assert strategy.risk_percent == Decimal("1.5")
    content = response.content.decode()
    assert 'id="profile-strategies-content"' in content
    assert 'hx-swap-oob="outerHTML"' in content
    trigger = response.headers["HX-Trigger"]
    assert "Strategy created." in trigger
    assert "strategy-create-modal" in trigger


@mark.django_db
def test_create_strategy_rejects_non_positive_risk() -> None:
    client, _owner, profile, _wallet, _eligible = _journal_chain()
    with override("en"):
        response = client.post(
            reverse("journal:strategy_create", args=(profile.pk,)),
            {
                "name": "Bad",
                "description": "",
                "risk_percent": "0",
                "reward_multiple": "3",
            },
        )

    assert response.status_code == 422
    assert "Risk percent must be positive." in response.content.decode()
    assert not TradingStrategy.objects.filter(profile=profile).exists()


@mark.django_db
def test_edit_strategy_updates_fields() -> None:
    client, _owner, profile, _wallet, _eligible = _journal_chain()
    strategy = _strategy(profile)
    with override("en"):
        response = client.post(
            reverse("journal:strategy_edit", args=(profile.pk, strategy.pk)),
            {
                "name": "Scalp",
                "description": "quick",
                "risk_percent": "2",
                "reward_multiple": "2",
            },
        )

    strategy.refresh_from_db()
    assert strategy.name == "Scalp"
    assert strategy.description == "quick"
    assert strategy.risk_percent == Decimal(1)
    assert strategy.reward_multiple == Decimal(3)
    assert response.status_code == 200
    assert "Strategy updated." in response.headers["HX-Trigger"]


@mark.django_db
def test_archive_get_returns_confirm_without_archiving() -> None:
    client, _owner, profile, _wallet, _eligible = _journal_chain()
    strategy = _strategy(profile)
    with override("en"):
        response = client.get(
            reverse("journal:strategy_archive", args=(profile.pk, strategy.pk))
        )

    assert response.status_code == 200
    strategy.refresh_from_db()
    assert strategy.status == "active"
    content = response.content.decode()
    assert "Archive the strategy" in content
    assert f'hx-post="{reverse("journal:strategy_archive", args=(profile.pk, strategy.pk))}"' in content


@mark.django_db
def test_archive_and_restore_strategy() -> None:
    client, _owner, profile, _wallet, _eligible = _journal_chain()
    strategy = _strategy(profile)
    with override("en"):
        archive = client.post(
            reverse("journal:strategy_archive", args=(profile.pk, strategy.pk))
        )
        strategy.refresh_from_db()
        assert strategy.status == "archived"
        restore = client.post(
            reverse("journal:strategy_restore", args=(profile.pk, strategy.pk))
        )

    strategy.refresh_from_db()
    assert strategy.status == "active"
    assert "Strategy archived." in archive.headers["HX-Trigger"]
    assert "Strategy restored." in restore.headers["HX-Trigger"]


@mark.django_db
def test_allocation_form_offers_only_settlement_assets() -> None:
    _client, _owner, profile, wallet, eligible = _journal_chain()
    ineligible_asset = _asset("ETH")
    ineligible = _venue_wallet_asset(profile.venue, ineligible_asset)
    _wallet_asset(wallet, ineligible)
    strategy = _strategy(profile)
    form = StrategyCapitalForm(strategy=strategy)

    offered = list(form.fields["wallet_asset"].queryset.values_list("id", flat=True))
    assert eligible.pk in offered
    assert ineligible.pk not in offered


@mark.django_db
def test_add_allocation_creates_capital() -> None:
    client, _owner, profile, _wallet, eligible = _journal_chain()
    strategy = _strategy(profile)
    with override("en"):
        response = client.post(
            reverse("journal:strategy_capital_add", args=(profile.pk, strategy.pk)),
            {"wallet_asset": eligible.pk, "capital": "1000"},
        )

    assert response.status_code == 200
    allocation = StrategyCapital.objects.get(strategy=strategy)
    assert allocation.wallet_asset == eligible
    assert allocation.capital == Decimal(1000)
    content = response.content.decode()
    assert "USDT" in content
    trigger = response.headers["HX-Trigger"]
    assert "Allocation added." in trigger


@mark.django_db
def test_add_duplicate_allocation_returns_422() -> None:
    client, _owner, profile, _wallet, eligible = _journal_chain()
    strategy = _strategy(profile)
    StrategyCapital.objects.create(
        strategy=strategy, wallet_asset=eligible, capital=Decimal(100)
    )
    with override("en"):
        response = client.post(
            reverse("journal:strategy_capital_add", args=(profile.pk, strategy.pk)),
            {"wallet_asset": eligible.pk, "capital": "200"},
        )

    assert response.status_code == 422
    assert StrategyCapital.objects.count() == 1


@mark.django_db
def test_archive_and_restore_allocation() -> None:
    client, _owner, profile, _wallet, eligible = _journal_chain()
    strategy = _strategy(profile)
    allocation = StrategyCapital.objects.create(
        strategy=strategy, wallet_asset=eligible, capital=Decimal(100)
    )
    with override("en"):
        archive = client.post(
            reverse(
                "journal:strategy_capital_archive",
                args=(profile.pk, strategy.pk, allocation.pk),
            )
        )
        allocation.refresh_from_db()
        assert allocation.status == "archived"
        restore = client.post(
            reverse(
                "journal:strategy_capital_restore",
                args=(profile.pk, strategy.pk, allocation.pk),
            )
        )

    allocation.refresh_from_db()
    assert allocation.status == "active"
    assert StrategyCapital.objects.filter(pk=allocation.pk).exists()
    assert "Allocation archived." in archive.headers["HX-Trigger"]
    assert "Allocation restored." in restore.headers["HX-Trigger"]


@mark.django_db
def test_archive_allocation_refused_with_unfinished_trade() -> None:
    client, _owner, profile, _wallet, eligible = _journal_chain()
    strategy = _strategy(profile)
    allocation = StrategyCapital.objects.create(
        strategy=strategy, wallet_asset=eligible, capital=Decimal(100)
    )
    _submitted_trade(strategy, status="open")
    with override("en"):
        response = client.post(
            reverse(
                "journal:strategy_capital_archive",
                args=(profile.pk, strategy.pk, allocation.pk),
            )
        )

    assert response.status_code == 409
    allocation.refresh_from_db()
    assert allocation.status == "active"
    assert "Cancel or wait" in response.headers["HX-Trigger"]


@mark.django_db
def test_archive_allocation_allowed_with_closed_trade() -> None:
    client, _owner, profile, _wallet, eligible = _journal_chain()
    strategy = _strategy(profile)
    allocation = StrategyCapital.objects.create(
        strategy=strategy, wallet_asset=eligible, capital=Decimal(100)
    )
    _submitted_trade(strategy, status="closed")
    with override("en"):
        response = client.post(
            reverse(
                "journal:strategy_capital_archive",
                args=(profile.pk, strategy.pk, allocation.pk),
            )
        )

    assert response.status_code == 200
    allocation.refresh_from_db()
    assert allocation.status == "archived"


@mark.django_db
def test_archived_allocation_keeps_its_slot() -> None:
    _client, _owner, profile, _wallet, eligible = _journal_chain()
    strategy = _strategy(profile)
    StrategyCapital.objects.create(
        strategy=strategy, wallet_asset=eligible, capital=Decimal(100)
    )
    form = StrategyCapitalForm(strategy=strategy)
    offered = list(form.fields["wallet_asset"].queryset.values_list("id", flat=True))
    assert eligible.pk not in offered


@mark.django_db
def test_strategy_detail_modal_renders_allocations() -> None:
    client, _owner, profile, _wallet, eligible = _journal_chain()
    strategy = _strategy(profile)
    StrategyCapital.objects.create(
        strategy=strategy, wallet_asset=eligible, capital=Decimal(500)
    )
    with override("en"):
        response = client.get(
            reverse("journal:strategy_detail", args=(profile.pk, strategy.pk))
        )

    content = response.content.decode()
    assert "USDT" in content
    assert "500" in content
    assert "Add allocation" in content


@mark.django_db
def test_strategy_detail_shows_empty_state_when_no_assets_remain() -> None:
    client, _owner, profile, _wallet, eligible = _journal_chain()
    strategy = _strategy(profile)
    StrategyCapital.objects.create(
        strategy=strategy, wallet_asset=eligible, capital=Decimal(100)
    )
    with override("en"):
        response = client.get(
            reverse("journal:strategy_detail", args=(profile.pk, strategy.pk))
        )

    content = response.content.decode()
    assert "All assets are already allocated" in content
    assert (
        "Every available settlement asset already backs this strategy."
        in content
    )
    assert 'name="wallet_asset"' not in content


@mark.django_db
def test_strategies_table_paginates() -> None:
    client, _owner, profile, _wallet, _eligible = _journal_chain()
    for number in range(1, 12):
        _strategy(profile, name=f"S{number:02d}")
    with override("en"):
        response = client.get(
            reverse("journal:profile_detail", args=(profile.pk,))
        )

    assert "Page 1 of 2" in response.content.decode()


@mark.django_db
def test_strategy_actions_are_owner_scoped() -> None:
    _client, _owner, profile, _wallet, _eligible = _journal_chain()
    strategy = _strategy(profile)
    intruder = _login_as("intruder")
    with override("en"):
        create = intruder.post(
            reverse("journal:strategy_create", args=(profile.pk,)),
            {"name": "Hack", "risk_percent": "1", "reward_multiple": "3"},
        )
        edit = intruder.post(
            reverse("journal:strategy_edit", args=(profile.pk, strategy.pk)),
            {"name": "Hack", "risk_percent": "1", "reward_multiple": "3"},
        )

    assert create.status_code == 404
    assert edit.status_code == 404
    assert TradingStrategy.objects.filter(profile=profile).count() == 1


@mark.django_db
def test_archived_profile_strategies_are_readonly() -> None:
    client, owner = _owner_client()
    profile = _profile(owner, _venue(), archived=True)
    strategy = _strategy(profile)
    with override("en"):
        response = client.post(
            reverse("journal:strategy_archive", args=(profile.pk, strategy.pk))
        )

    assert response.status_code == 409
    strategy.refresh_from_db()
    assert strategy.status == "active"
    assert "Restore the profile to manage its strategies." in (
        response.headers["HX-Trigger"]
    )


@mark.django_db
def test_strategies_tab_renders_in_russian() -> None:
    client, owner = _owner_client()
    profile = _profile(owner, _venue())
    with override("ru"):
        response = client.get(
            reverse("journal:profile_detail", args=(profile.pk,))
        )

    content = response.content.decode()
    assert "Стратегий пока нет" in content
    assert "Добавить стратегию" in content


@mark.django_db
def test_strategy_create_toast_renders_in_russian() -> None:
    client, _owner, profile, _wallet, _eligible = _journal_chain()
    with override("ru"):
        response = client.post(
            reverse("journal:strategy_create", args=(profile.pk,)),
            {"name": "Breakout", "risk_percent": "1", "reward_multiple": "3"},
        )

    assert response.status_code == 200
    trigger = json.loads(response.headers["HX-Trigger"])
    assert trigger["tradefog:toast"]["message"] == "Стратегия создана."
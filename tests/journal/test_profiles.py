"""Tests for profile and instrument workflows."""

from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import Client
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import override
from pytest import mark, raises

from tradefog.accounts.models import User
from tradefog.journal.models import ProfileInstrument, TradingProfile
from tradefog.journal.services import archive_profile


def profile_data(**overrides: str) -> dict[str, str]:
    """Return a complete valid profile form payload."""
    data = {
        "name": "Primary",
        "capital_currency": "usd",
        "initial_capital": "10000",
        "risk_per_trade_percent": "1",
        "risk_stop_capital": "9000",
    }
    data.update(overrides)
    return data


def instrument_data(**overrides: str) -> dict[str, str]:
    """Return a complete valid instrument form payload."""
    data = {
        "base_asset": "btc",
        "display_name": "Bitcoin",
        "market_type": ProfileInstrument.MarketType.SPOT,
        "price_step": "0.01",
        "quantity_step": "0.00001",
        "minimum_quantity": "0.0001",
        "minimum_notional": "10",
    }
    data.update(overrides)
    return data


def create_profile(owner: User, name: str = "Primary") -> TradingProfile:
    """Create a profile with the baseline risk configuration."""
    return TradingProfile.objects.create(
        owner=owner,
        name=name,
        capital_currency="USD",
        initial_capital=Decimal(10000),
        risk_stop_capital=Decimal(9000),
    )


@mark.django_db
def test_user_creates_normalized_profile() -> None:
    """Profile creation should assign its owner and normalize currency."""
    user = User.objects.create_user(username="trader")
    client = Client()
    client.force_login(user)

    response = client.post("/en/profiles/new/", profile_data())

    profile = TradingProfile.objects.get()
    assert response.status_code == 302
    assert response.headers["Location"] == f"/en/profiles/{profile.id}/"
    assert profile.owner == user
    assert profile.capital_currency == "USD"
    assert profile.provider == TradingProfile.Provider.MANUAL
    assert profile.risk_per_trade_percent == Decimal("1.000")
    assert profile.risk_stop_capital == Decimal("9000.00000000")
    assert profile.status == TradingProfile.Status.ACTIVE.value


@mark.django_db
def test_profile_overview_is_owner_scoped() -> None:
    """The global overview should never reveal another user's profile."""
    owner = User.objects.create_user(username="owner")
    stranger = User.objects.create_user(username="stranger")
    _ = create_profile(owner, "Visible profile")
    _ = create_profile(stranger, "Private profile")
    client = Client()
    client.force_login(owner)

    response = client.get("/en/profiles/")
    content = response.content.decode()

    assert response.status_code == 200
    assert "Visible profile" in content
    assert "Private profile" not in content


@mark.django_db
def test_foreign_profile_routes_return_not_found() -> None:
    """Read and mutation routes should enforce the owner boundary."""
    owner = User.objects.create_user(username="owner")
    stranger = User.objects.create_user(username="stranger")
    profile = create_profile(owner)
    client = Client()
    client.force_login(stranger)

    paths = [
        f"/en/profiles/{profile.id}/",
        f"/en/profiles/{profile.id}/edit/",
        f"/en/profiles/{profile.id}/archive/",
        f"/en/profiles/{profile.id}/instruments/new/",
    ]

    assert all(client.get(path).status_code == 404 for path in paths)


@mark.django_db
def test_profile_stop_must_be_below_current_capital() -> None:
    """A new profile should not begin at or beyond its stop threshold."""
    user = User.objects.create_user(username="trader")
    client = Client()
    client.force_login(user)

    response = client.post(
        "/en/profiles/new/",
        profile_data(risk_stop_capital="11000"),
    )

    assert response.status_code == 200
    assert not TradingProfile.objects.exists()
    assert b"Risk stop must be lower than current capital" in response.content


@mark.django_db
def test_profile_form_exposes_only_current_strategy_configuration() -> None:
    """The form should not expose provider or removed period settings."""
    user = User.objects.create_user(username="trader")
    client = Client()
    client.force_login(user)

    response = client.get("/en/profiles/new/")

    assert response.status_code == 200
    assert b'name="provider"' not in response.content
    assert b'name="reward_multiple"' not in response.content
    assert b'name="daily_risk_limit_percent"' not in response.content
    assert b'name="monthly_target_percent"' not in response.content
    assert b"1:3" in response.content
    assert b"Bybit (coming later)" in response.content
    assert b"disabled" in response.content


@mark.django_db
def test_editing_absolute_stop_recalculates_profile_status() -> None:
    """The mutable stop should immediately update operational state."""
    user = User.objects.create_user(username="trader")
    profile = create_profile(user)
    profile.risk_stop_capital = Decimal(10000)
    profile.status = TradingProfile.Status.RISK_STOPPED.value
    profile.save(update_fields=["risk_stop_capital", "status"])
    client = Client()
    client.force_login(user)

    response = client.post(
        f"/en/profiles/{profile.id}/edit/",
        profile_data(risk_stop_capital="9000"),
    )

    profile.refresh_from_db()
    assert response.status_code == 302
    assert profile.risk_stop_capital == Decimal("9000.00000000")
    assert profile.status == TradingProfile.Status.ACTIVE.value


@mark.django_db
def test_profile_form_compacts_stored_decimal_values() -> None:
    """Editing should show meaningful digits rather than storage padding."""
    user = User.objects.create_user(username="trader")
    profile = create_profile(user)
    client = Client()
    client.force_login(user)

    response = client.get(f"/en/profiles/{profile.id}/edit/")

    assert response.status_code == 200
    assert b'value="10000"' in response.content
    assert b'value="9000"' in response.content
    assert b'value="1"' in response.content
    assert b'value="10000.00000000"' not in response.content


@mark.django_db
def test_profile_can_be_edited_and_archived_without_deletion() -> None:
    """Editing should preserve ownership and archive should retain the row."""
    user = User.objects.create_user(username="trader")
    profile = create_profile(user)
    client = Client()
    client.force_login(user)

    edit_response = client.post(
        f"/en/profiles/{profile.id}/edit/",
        profile_data(name="Conservative"),
    )
    archive_response = client.post(f"/en/profiles/{profile.id}/archive/")

    profile.refresh_from_db()
    assert edit_response.status_code == 302
    assert archive_response.headers["Location"] == "/en/profiles/"
    assert profile.name == "Conservative"
    assert profile.owner == user
    assert profile.archived_at is not None
    assert profile.status == TradingProfile.Status.ARCHIVED.value
    assert TradingProfile.objects.filter(id=profile.id).exists()
    assert client.get(f"/en/profiles/{profile.id}/").status_code == 404


@mark.django_db
def test_capital_currency_is_locked_after_adding_an_instrument() -> None:
    """Existing markets must retain the profile settlement asset."""
    user = User.objects.create_user(username="trader")
    profile = create_profile(user)
    _ = ProfileInstrument.objects.create(
        profile=profile,
        base_asset="BTC",
        price_step=Decimal("0.01"),
        quantity_step=Decimal("0.001"),
    )
    client = Client()
    client.force_login(user)

    form_response = client.get(f"/en/profiles/{profile.id}/edit/")
    post_response = client.post(
        f"/en/profiles/{profile.id}/edit/",
        profile_data(capital_currency="EUR"),
    )

    profile.refresh_from_db()
    assert b'name="capital_currency"' in form_response.content
    assert b"disabled" in form_response.content
    assert post_response.status_code == 302
    assert profile.capital_currency == "USD"

    profile.capital_currency = "EUR"
    with raises(ValidationError):
        profile.full_clean()


@mark.django_db
def test_archived_profile_is_listed_and_can_be_restored() -> None:
    """An owner should be able to recover an archived profile."""
    user = User.objects.create_user(username="trader")
    profile = create_profile(user)
    archive_profile(profile)
    client = Client()
    client.force_login(user)

    archive_response = client.get("/en/profiles/archived/")
    restore_response = client.post(f"/en/profiles/{profile.id}/restore/")
    message_response = client.get(profile.get_absolute_url())

    profile.refresh_from_db()
    assert archive_response.status_code == 200
    assert profile.name in archive_response.content.decode()
    assert restore_response.status_code == 302
    assert restore_response.headers["Location"] == profile.get_absolute_url()
    assert b"Profile restored." in message_response.content
    assert b"alert-dismissible" in message_response.content
    assert b'data-bs-dismiss="alert"' in message_response.content
    assert profile.archived_at is None
    assert profile.status == TradingProfile.Status.ACTIVE.value


@mark.django_db
def test_profile_restore_is_owner_scoped_and_post_only() -> None:
    """Restoration must not expose or mutate another owner's profile."""
    owner = User.objects.create_user(username="owner")
    stranger = User.objects.create_user(username="stranger")
    profile = create_profile(owner)
    archive_profile(profile)
    client = Client()
    client.force_login(stranger)

    path = f"/en/profiles/{profile.id}/restore/"

    assert client.get(path).status_code == 405
    assert client.post(path).status_code == 404


@mark.django_db
def test_user_adds_normalized_instrument_to_profile() -> None:
    """Instrument creation should use the profile from the owned URL."""
    user = User.objects.create_user(username="trader")
    profile = create_profile(user)
    client = Client()
    client.force_login(user)

    response = client.post(
        f"/en/profiles/{profile.id}/instruments/new/",
        instrument_data(),
    )

    instrument = ProfileInstrument.objects.get()
    assert response.status_code == 302
    assert response.headers["Location"] == profile.get_absolute_url()
    assert instrument.profile == profile
    assert instrument.base_asset == "BTC"
    assert instrument.symbol == "BTC/USD"
    assert instrument.price_step == Decimal("0.010000000000")


@mark.django_db
def test_instrument_form_accepts_only_a_base_asset() -> None:
    """The quote asset must always come from the selected profile."""
    user = User.objects.create_user(username="trader")
    profile = create_profile(user)
    client = Client()
    client.force_login(user)

    response = client.post(
        f"/en/profiles/{profile.id}/instruments/new/",
        instrument_data(base_asset="BTC/USDT"),
    )

    assert response.status_code == 200
    assert not ProfileInstrument.objects.exists()
    assert b"letters, numbers, dots, underscores, or hyphens" in (
        response.content
    )


@mark.django_db
def test_base_asset_must_differ_from_profile_capital() -> None:
    """A profile cannot contain a market that trades an asset for itself."""
    user = User.objects.create_user(username="trader")
    profile = create_profile(user)
    client = Client()
    client.force_login(user)

    response = client.post(
        f"/en/profiles/{profile.id}/instruments/new/",
        instrument_data(base_asset="usd"),
    )

    assert response.status_code == 200
    assert not ProfileInstrument.objects.exists()
    assert b"must differ from the capital asset" in response.content


@mark.django_db
def test_spot_and_linear_markets_can_share_a_base_asset() -> None:
    """Market type distinguishes instruments with the same canonical pair."""
    user = User.objects.create_user(username="trader")
    profile = create_profile(user)
    _ = ProfileInstrument.objects.create(
        profile=profile,
        base_asset="BTC",
        market_type=ProfileInstrument.MarketType.SPOT,
        price_step=Decimal("0.01"),
        quantity_step=Decimal("0.001"),
    )
    client = Client()
    client.force_login(user)

    response = client.post(
        f"/en/profiles/{profile.id}/instruments/new/",
        instrument_data(
            base_asset="btc",
            market_type=ProfileInstrument.MarketType.LINEAR,
        ),
    )

    assert response.status_code == 302
    assert ProfileInstrument.objects.filter(base_asset="BTC").count() == 2


@mark.django_db
def test_duplicate_active_market_is_rejected_but_archived_market_is_reusable() -> (
    None
):
    """Only active instruments should reserve their normalized market."""
    user = User.objects.create_user(username="trader")
    profile = create_profile(user)
    existing = ProfileInstrument.objects.create(
        profile=profile,
        base_asset="BTC",
        market_type=ProfileInstrument.MarketType.SPOT,
        price_step=Decimal("0.01"),
        quantity_step=Decimal("0.00001"),
    )
    client = Client()
    client.force_login(user)

    duplicate_response = client.post(
        f"/en/profiles/{profile.id}/instruments/new/",
        instrument_data(base_asset="btc"),
    )
    archive_response = client.post(
        f"/en/profiles/{profile.id}/instruments/{existing.id}/archive/"
    )
    replacement_response = client.post(
        f"/en/profiles/{profile.id}/instruments/new/",
        instrument_data(base_asset="btc"),
    )

    assert duplicate_response.status_code == 200
    assert b"active instrument already uses this market" in (
        duplicate_response.content
    )
    assert archive_response.status_code == 302
    assert replacement_response.status_code == 302
    assert ProfileInstrument.objects.filter(base_asset="BTC").count() == 2


@mark.django_db
def test_archived_instrument_can_be_restored() -> None:
    """Restoration should make an archived instrument active again."""
    user = User.objects.create_user(username="trader")
    profile = create_profile(user)
    instrument = ProfileInstrument.objects.create(
        profile=profile,
        base_asset="ETH",
        price_step=Decimal("0.01"),
        quantity_step=Decimal("0.001"),
        archived_at=timezone.now(),
    )
    client = Client()
    client.force_login(user)

    detail_response = client.get(profile.get_absolute_url())
    restore_response = client.post(
        f"/en/profiles/{profile.id}/instruments/{instrument.id}/restore/"
    )

    instrument.refresh_from_db()
    assert b"Archived instruments" in detail_response.content
    assert restore_response.status_code == 302
    assert instrument.archived_at is None


@mark.django_db
def test_instrument_restore_reports_active_market_conflict() -> None:
    """An archived market cannot displace an existing active instrument."""
    user = User.objects.create_user(username="trader")
    profile = create_profile(user)
    archived = ProfileInstrument.objects.create(
        profile=profile,
        base_asset="ETH",
        price_step=Decimal("0.01"),
        quantity_step=Decimal("0.001"),
        archived_at=timezone.now(),
    )
    _ = ProfileInstrument.objects.create(
        profile=profile,
        base_asset="ETH",
        price_step=Decimal("0.01"),
        quantity_step=Decimal("0.001"),
    )
    client = Client()
    client.force_login(user)

    response = client.post(
        f"/en/profiles/{profile.id}/instruments/{archived.id}/restore/",
        follow=True,
    )

    archived.refresh_from_db()
    assert archived.archived_at is not None
    assert b"active instrument already uses this market" in response.content


@mark.django_db
def test_instrument_routes_require_matching_owned_profile() -> None:
    """An instrument ID cannot be used through another profile's URL."""
    user = User.objects.create_user(username="trader")
    first_profile = create_profile(user, "First")
    second_profile = create_profile(user, "Second")
    instrument = ProfileInstrument.objects.create(
        profile=first_profile,
        base_asset="ETH",
        price_step=Decimal("0.01"),
        quantity_step=Decimal("0.001"),
    )
    client = Client()
    client.force_login(user)

    edit_path = (
        f"/en/profiles/{second_profile.id}/instruments/{instrument.id}/edit/"
    )
    archive_path = (
        f"/en/profiles/{second_profile.id}/instruments/"
        f"{instrument.id}/archive/"
    )

    assert client.get(edit_path).status_code == 404
    assert client.post(archive_path).status_code == 404


def test_journal_routes_follow_the_active_language() -> None:
    """Every journal action should retain the explicit language prefix."""
    with override("en"):
        assert reverse("profile_overview") == "/en/profiles/"
        assert reverse("profile_create") == "/en/profiles/new/"
        assert reverse("profile_detail", args=[7]) == "/en/profiles/7/"
        assert reverse("archived_profile_overview") == (
            "/en/profiles/archived/"
        )
        assert reverse("instrument_create", args=[7]) == (
            "/en/profiles/7/instruments/new/"
        )
        assert reverse("capital_deposit", args=[7]) == (
            "/en/profiles/7/capital/deposit/"
        )

    with override("ru"):
        assert reverse("profile_overview") == "/ru/profiles/"
        assert reverse("profile_create") == "/ru/profiles/new/"
        assert reverse("profile_detail", args=[7]) == "/ru/profiles/7/"
        assert reverse("instrument_create", args=[7]) == (
            "/ru/profiles/7/instruments/new/"
        )
        assert reverse("capital_withdraw", args=[7]) == (
            "/ru/profiles/7/capital/withdraw/"
        )

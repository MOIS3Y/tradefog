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


def profile_data(**overrides: str) -> dict[str, str]:
    """Return a complete valid profile form payload."""
    data = {
        "name": "Primary",
        "venue_name": "Kraken",
        "capital_currency": "usd",
        "initial_capital": "10000",
        "risk_per_trade_percent": "0.33",
        "reward_multiple": "3",
        "daily_risk_limit_percent": "1",
        "monthly_target_percent": "3",
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
        venue_name="Kraken",
        capital_currency="USD",
        initial_capital=Decimal(10000),
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
    assert profile.risk_per_trade_percent == Decimal("0.330")
    assert profile.reward_multiple == Decimal("3.00")


@mark.django_db
def test_profile_overview_is_owner_scoped() -> None:
    """The global overview should never reveal another user's profile."""
    owner = User.objects.create_user(username="owner")
    stranger = User.objects.create_user(username="stranger")
    _ = create_profile(owner, "Visible profile")
    _ = create_profile(stranger, "Private profile")
    client = Client()
    client.force_login(owner)

    response = client.get("/en/")
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
def test_profile_validation_explains_inconsistent_daily_risk() -> None:
    """A daily budget below one trade's risk should be rejected in place."""
    user = User.objects.create_user(username="trader")
    client = Client()
    client.force_login(user)

    response = client.post(
        "/en/profiles/new/",
        profile_data(
            risk_per_trade_percent="1",
            daily_risk_limit_percent="0.33",
        ),
    )

    assert response.status_code == 200
    assert not TradingProfile.objects.exists()
    assert b"daily risk limit cannot be lower" in response.content
    assert b"tf-field-invalid" in response.content


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
    assert archive_response.headers["Location"] == "/en/"
    assert profile.name == "Conservative"
    assert profile.owner == user
    assert profile.archived_at is not None
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
    profile.archived_at = timezone.now()
    profile.save(update_fields=["archived_at"])
    client = Client()
    client.force_login(user)

    archive_response = client.get("/en/profiles/archived/")
    restore_response = client.post(f"/en/profiles/{profile.id}/restore/")

    profile.refresh_from_db()
    assert archive_response.status_code == 200
    assert profile.name in archive_response.content.decode()
    assert restore_response.status_code == 302
    assert restore_response.headers["Location"] == profile.get_absolute_url()
    assert profile.archived_at is None


@mark.django_db
def test_profile_restore_is_owner_scoped_and_post_only() -> None:
    """Restoration must not expose or mutate another owner's profile."""
    owner = User.objects.create_user(username="owner")
    stranger = User.objects.create_user(username="stranger")
    profile = create_profile(owner)
    profile.archived_at = timezone.now()
    profile.save(update_fields=["archived_at"])
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
        assert reverse("profile_create") == "/en/profiles/new/"
        assert reverse("profile_detail", args=[7]) == "/en/profiles/7/"
        assert reverse("archived_profile_overview") == (
            "/en/profiles/archived/"
        )
        assert reverse("instrument_create", args=[7]) == (
            "/en/profiles/7/instruments/new/"
        )

    with override("ru"):
        assert reverse("profile_create") == "/ru/profiles/new/"
        assert reverse("profile_detail", args=[7]) == "/ru/profiles/7/"
        assert reverse("instrument_create", args=[7]) == (
            "/ru/profiles/7/instruments/new/"
        )

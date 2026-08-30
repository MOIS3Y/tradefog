"""Tests for virtual profile capital and operational status."""

from decimal import Decimal

from django.test import Client
from pytest import mark

from tradefog.accounts.models import User
from tradefog.journal.models import Asset, CapitalOperation, TradingProfile
from tradefog.journal.services import archive_profile, restore_profile

DEFAULT_INITIAL_CAPITAL = Decimal(10000)
DEFAULT_RISK_STOP_CAPITAL = Decimal(9000)


def create_profile(
    owner: User,
    *,
    initial_capital: Decimal = DEFAULT_INITIAL_CAPITAL,
    risk_stop_capital: Decimal = DEFAULT_RISK_STOP_CAPITAL,
) -> TradingProfile:
    """Create a manual profile with round risk values."""
    capital_asset, _created = Asset.objects.get_or_create(
        owner=owner,
        symbol="USDT",
    )
    return TradingProfile.objects.create(
        owner=owner,
        name="Primary",
        capital_asset=capital_asset,
        initial_capital=initial_capital,
        risk_per_trade_percent=Decimal(1),
        risk_stop_capital=risk_stop_capital,
    )


@mark.django_db
def test_deposit_changes_current_capital_without_rewriting_initial_capital() -> (
    None
):
    """A deposit should append a fact and expand future risk."""
    user = User.objects.create_user(username="trader")
    profile = create_profile(user)
    client = Client()
    client.force_login(user)

    response = client.post(
        f"/en/profiles/{profile.id}/capital/deposit/",
        {"amount": "2000", "note": "Additional allocation"},
    )

    profile.refresh_from_db()
    operation = CapitalOperation.objects.get()
    assert response.status_code == 302
    assert profile.initial_capital == Decimal("10000.00000000")
    assert profile.current_capital == Decimal("12000.00000000")
    assert profile.risk_base == Decimal("12000.00000000")
    assert profile.risk_amount == Decimal("120.00000000000")
    assert profile.status == TradingProfile.Status.ACTIVE.value
    assert operation.operation_type == CapitalOperation.Type.DEPOSIT.value
    assert operation.note == "Additional allocation"


@mark.django_db
def test_withdrawal_can_explicitly_trigger_risk_stop() -> None:
    """Withdrawing allocated capital may deliberately stop the profile."""
    user = User.objects.create_user(username="trader")
    profile = create_profile(user)
    client = Client()
    client.force_login(user)

    response = client.post(
        f"/en/profiles/{profile.id}/capital/withdraw/",
        {"amount": "1500", "note": "Protected funds"},
    )

    profile.refresh_from_db()
    assert response.status_code == 302
    assert profile.current_capital == Decimal("8500.00000000")
    assert profile.risk_base == Decimal("10000.00000000")
    assert profile.risk_amount == Decimal("100.00000000000")
    assert profile.status == TradingProfile.Status.RISK_STOPPED.value


@mark.django_db
def test_stop_can_protect_growth_above_initial_capital() -> None:
    """A raised stop is valid when it remains below current capital."""
    user = User.objects.create_user(username="trader")
    profile = create_profile(user)
    _ = CapitalOperation.objects.create(
        profile=profile,
        operation_type=CapitalOperation.Type.DEPOSIT.value,
        amount=Decimal(2000),
    )
    client = Client()
    client.force_login(user)

    response = client.post(
        f"/en/profiles/{profile.id}/edit/",
        {
            "name": profile.name,
            "capital_asset": str(profile.capital_asset_id),
            "market_type": profile.market_type,
            "initial_capital": "10000",
            "risk_per_trade_percent": "1",
            "risk_stop_capital": "11000",
        },
    )

    profile.refresh_from_db()
    assert response.status_code == 302
    assert profile.current_capital == Decimal("12000.00000000")
    assert profile.risk_stop_capital == Decimal("11000.00000000")
    assert profile.status == TradingProfile.Status.ACTIVE.value


@mark.django_db
def test_withdrawal_cannot_create_artificial_negative_capital() -> None:
    """The allocation ledger should reject a withdrawal beyond capital."""
    user = User.objects.create_user(username="trader")
    profile = create_profile(user)
    client = Client()
    client.force_login(user)

    response = client.post(
        f"/en/profiles/{profile.id}/capital/withdraw/",
        {"amount": "10001", "note": "Too much"},
    )

    assert response.status_code == 200
    assert not CapitalOperation.objects.exists()
    assert b"make the profile capital negative" in response.content
    assert b"tf-field-invalid" in response.content


@mark.django_db
def test_operation_correction_recalculates_capital_and_status() -> None:
    """Correcting a typo should update current state without backdating."""
    user = User.objects.create_user(username="trader")
    profile = create_profile(user)
    operation = CapitalOperation.objects.create(
        profile=profile,
        operation_type=CapitalOperation.Type.WITHDRAWAL.value,
        amount=Decimal(1500),
        note="Typo",
    )
    profile.status = TradingProfile.Status.RISK_STOPPED.value
    profile.save(update_fields=["status"])
    client = Client()
    client.force_login(user)

    response = client.post(
        f"/en/profiles/{profile.id}/capital/{operation.id}/edit/",
        {"amount": "500", "note": "Corrected"},
    )

    profile.refresh_from_db()
    operation.refresh_from_db()
    assert response.status_code == 302
    assert operation.operation_type == CapitalOperation.Type.WITHDRAWAL.value
    assert operation.amount == Decimal("500.00000000")
    assert operation.note == "Corrected"
    assert profile.current_capital == Decimal("9500.00000000")
    assert profile.status == TradingProfile.Status.ACTIVE.value


@mark.django_db
def test_deleting_required_deposit_is_rejected() -> None:
    """Removing a deposit cannot leave withdrawals as artificial debt."""
    user = User.objects.create_user(username="trader")
    profile = create_profile(user)
    deposit = CapitalOperation.objects.create(
        profile=profile,
        operation_type=CapitalOperation.Type.DEPOSIT.value,
        amount=Decimal(1000),
    )
    _ = CapitalOperation.objects.create(
        profile=profile,
        operation_type=CapitalOperation.Type.WITHDRAWAL.value,
        amount=Decimal(10500),
    )
    client = Client()
    client.force_login(user)

    response = client.post(
        f"/en/profiles/{profile.id}/capital/{deposit.id}/delete/",
        follow=True,
    )

    assert response.status_code == 200
    assert CapitalOperation.objects.filter(id=deposit.id).exists()
    assert b"make the profile capital negative" in response.content


@mark.django_db
def test_capital_operation_routes_enforce_profile_ownership() -> None:
    """Capital facts must remain inside their owner's profile boundary."""
    owner = User.objects.create_user(username="owner")
    stranger = User.objects.create_user(username="stranger")
    profile = create_profile(owner)
    operation = CapitalOperation.objects.create(
        profile=profile,
        operation_type=CapitalOperation.Type.DEPOSIT.value,
        amount=Decimal(100),
    )
    client = Client()
    client.force_login(stranger)

    assert (
        client.post(
            f"/en/profiles/{profile.id}/capital/deposit/",
            {"amount": "1", "note": ""},
        ).status_code
        == 404
    )
    assert (
        client.get(
            f"/en/profiles/{profile.id}/capital/{operation.id}/edit/"
        ).status_code
        == 404
    )


@mark.django_db
def test_restoring_profile_recalculates_risk_status() -> None:
    """Archive state should not hide the current financial condition."""
    user = User.objects.create_user(username="trader")
    profile = create_profile(user, risk_stop_capital=Decimal(10000))
    archive_profile(profile)

    restore_profile(profile)

    profile.refresh_from_db()
    assert profile.archived_at is None
    assert profile.status == TradingProfile.Status.RISK_STOPPED.value

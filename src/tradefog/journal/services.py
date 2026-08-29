"""Focused state changes for profiles, capital, and instruments."""

from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from tradefog.journal.models import (
    CapitalOperation,
    ProfileInstrument,
    TradingProfile,
)

INSUFFICIENT_CAPITAL = _(
    "The operation would make the profile capital negative."
)
ZERO = Decimal(0)


def sync_profile_status(profile: TradingProfile) -> str:
    """Persist the status derived from the profile's financial facts."""
    calculated_status = profile.calculated_status
    if profile.status != calculated_status:
        profile.status = calculated_status
        profile.save(update_fields=["status", "updated_at"])
    return calculated_status


def archive_profile(profile: TradingProfile) -> None:
    """Archive a profile while retaining its journal configuration."""
    if profile.status == TradingProfile.Status.ARCHIVED.value:
        return
    profile.status = TradingProfile.Status.ARCHIVED.value
    profile.archived_at = timezone.now()
    profile.save(update_fields=["status", "archived_at", "updated_at"])


def restore_profile(profile: TradingProfile) -> None:
    """Restore a profile and derive its current financial status."""
    if profile.status != TradingProfile.Status.ARCHIVED.value:
        return
    profile.status = TradingProfile.Status.ACTIVE.value
    profile.archived_at = None
    profile.status = profile.calculated_status
    profile.save(update_fields=["status", "archived_at", "updated_at"])


def _projected_capital(
    profile: TradingProfile,
    *,
    removed_amount: Decimal = ZERO,
    added_amount: Decimal = ZERO,
) -> Decimal:
    """Return capital after replacing one signed operation contribution."""
    return profile.current_capital - removed_amount + added_amount


def _validate_projected_capital(
    current_capital: Decimal,
    projected_capital: Decimal,
) -> None:
    """Reject an allocation change that creates or worsens capital debt."""
    if projected_capital < 0 and projected_capital < current_capital:
        raise ValidationError({"amount": INSUFFICIENT_CAPITAL})


@transaction.atomic
def create_capital_operation(
    profile: TradingProfile,
    *,
    operation_type: str,
    amount: Decimal,
    note: str = "",
) -> CapitalOperation:
    """Apply one explicit allocation change and synchronize profile state."""
    locked_profile = TradingProfile.objects.select_for_update().get(
        id=profile.id
    )
    operation = CapitalOperation(
        profile=locked_profile,
        operation_type=operation_type,
        amount=amount,
        note=note,
    )
    operation.full_clean()
    _validate_projected_capital(
        locked_profile.current_capital,
        _projected_capital(
            locked_profile,
            added_amount=operation.signed_amount,
        ),
    )
    operation.save()
    _ = sync_profile_status(locked_profile)
    profile.refresh_from_db()
    return operation


@transaction.atomic
def update_capital_operation(
    operation: CapitalOperation,
    *,
    amount: Decimal,
    note: str,
) -> CapitalOperation:
    """Correct an allocation fact without changing its type or timestamp."""
    locked_operation = (
        CapitalOperation.objects.select_for_update()
        .select_related("profile")
        .get(id=operation.id)
    )
    profile = TradingProfile.objects.select_for_update().get(
        id=locked_operation.profile.id
    )
    previous_amount = locked_operation.signed_amount
    locked_operation.amount = amount
    locked_operation.note = note
    locked_operation.full_clean()
    _validate_projected_capital(
        profile.current_capital,
        _projected_capital(
            profile,
            removed_amount=previous_amount,
            added_amount=locked_operation.signed_amount,
        ),
    )
    locked_operation.save(update_fields=["amount", "note", "updated_at"])
    _ = sync_profile_status(profile)
    return locked_operation


@transaction.atomic
def delete_capital_operation(operation: CapitalOperation) -> None:
    """Remove an erroneous allocation fact when capital remains valid."""
    locked_operation = (
        CapitalOperation.objects.select_for_update()
        .select_related("profile")
        .get(id=operation.id)
    )
    profile = TradingProfile.objects.select_for_update().get(
        id=locked_operation.profile.id
    )
    _validate_projected_capital(
        profile.current_capital,
        _projected_capital(
            profile,
            removed_amount=locked_operation.signed_amount,
        ),
    )
    _ = locked_operation.delete()
    _ = sync_profile_status(profile)


def archive_instrument(instrument: ProfileInstrument) -> None:
    """Archive an instrument without deleting future trade references."""
    if instrument.archived_at is not None:
        return
    instrument.archived_at = timezone.now()
    instrument.save(update_fields=["archived_at", "updated_at"])


def restore_instrument(instrument: ProfileInstrument) -> bool:
    """Restore an instrument unless its active market is already in use."""
    if instrument.archived_at is None:
        return True
    try:
        with transaction.atomic():
            instrument.archived_at = None
            instrument.save(update_fields=["archived_at", "updated_at"])
    except IntegrityError:
        instrument.refresh_from_db()
        return False
    return True

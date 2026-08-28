"""Focused state changes for journal configuration objects."""

from django.db import IntegrityError, transaction
from django.utils import timezone

from tradefog.journal.models import ProfileInstrument, TradingProfile


def archive_profile(profile: TradingProfile) -> None:
    """Archive a profile without deleting its future journal history."""
    if profile.archived_at is not None:
        return
    profile.archived_at = timezone.now()
    profile.save(update_fields=["archived_at", "updated_at"])


def archive_instrument(instrument: ProfileInstrument) -> None:
    """Archive an instrument without deleting trades that may reference it."""
    if instrument.archived_at is not None:
        return
    instrument.archived_at = timezone.now()
    instrument.save(update_fields=["archived_at", "updated_at"])


def restore_profile(profile: TradingProfile) -> None:
    """Return an archived profile to active journal workflows."""
    if profile.archived_at is None:
        return
    profile.archived_at = None
    profile.save(update_fields=["archived_at", "updated_at"])


def restore_instrument(instrument: ProfileInstrument) -> bool:
    """Restore an instrument unless its active symbol is already in use."""
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

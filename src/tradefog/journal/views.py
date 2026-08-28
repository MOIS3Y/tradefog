"""Owner-scoped HTTP views for profiles and instruments."""

from typing import cast

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.translation import gettext as _
from django.views.decorators.http import require_http_methods, require_POST

from tradefog.accounts.models import User
from tradefog.journal.forms import ProfileInstrumentForm, TradingProfileForm
from tradefog.journal.models import (
    ACTIVE_MARKET_EXISTS,
    ProfileInstrument,
    TradingProfile,
)
from tradefog.journal.services import (
    archive_instrument,
    archive_profile,
    restore_instrument,
    restore_profile,
)


def _request_owner(request: HttpRequest) -> User:
    """Return the authenticated application user attached to a request."""
    return cast(User, request.user)


def _owned_profile(request: HttpRequest, profile_id: int) -> TradingProfile:
    """Resolve an active profile within the current ownership boundary."""
    return get_object_or_404(
        TradingProfile,
        id=profile_id,
        owner=_request_owner(request),
        archived_at__isnull=True,
    )


def _owned_archived_profile(
    request: HttpRequest,
    profile_id: int,
) -> TradingProfile:
    """Resolve an archived profile within the ownership boundary."""
    return get_object_or_404(
        TradingProfile,
        id=profile_id,
        owner=_request_owner(request),
        archived_at__isnull=False,
    )


def _owned_instrument(
    profile: TradingProfile,
    instrument_id: int,
) -> ProfileInstrument:
    """Resolve an active instrument belonging to the selected profile."""
    return get_object_or_404(
        ProfileInstrument,
        id=instrument_id,
        profile=profile,
        archived_at__isnull=True,
    )


def _owned_archived_instrument(
    profile: TradingProfile,
    instrument_id: int,
) -> ProfileInstrument:
    """Resolve an archived instrument belonging to an active profile."""
    return get_object_or_404(
        ProfileInstrument,
        id=instrument_id,
        profile=profile,
        archived_at__isnull=False,
    )


@login_required
def profile_overview(request: HttpRequest) -> HttpResponse:
    """List active profiles owned by the authenticated user."""
    profiles = TradingProfile.objects.filter(
        owner=_request_owner(request),
        archived_at__isnull=True,
    )
    return render(
        request,
        "tradefog/journal/profile_overview.html",
        {
            "profiles": profiles,
            "archived_profile_count": TradingProfile.objects.filter(
                owner=_request_owner(request),
                archived_at__isnull=False,
            ).count(),
        },
    )


@login_required
def archived_profile_overview(request: HttpRequest) -> HttpResponse:
    """List archived profiles owned by the authenticated user."""
    profiles = TradingProfile.objects.filter(
        owner=_request_owner(request),
        archived_at__isnull=False,
    )
    return render(
        request,
        "tradefog/journal/archived_profile_overview.html",
        {"profiles": profiles},
    )


@login_required
@require_http_methods(["GET", "POST"])
def profile_create(request: HttpRequest) -> HttpResponse:
    """Create a trading profile for the authenticated user."""
    form = TradingProfileForm(
        request.POST if request.method == "POST" else None
    )
    if request.method == "POST" and form.is_valid():
        profile = cast(TradingProfile, form.save(commit=False))
        profile.owner = _request_owner(request)
        profile.save()
        return redirect("profile_detail", profile_id=profile.id)
    return render(
        request,
        "tradefog/journal/profile_form.html",
        {"form": form, "editing": False},
    )


@login_required
def profile_detail(request: HttpRequest, profile_id: int) -> HttpResponse:
    """Show one profile and its active venue instruments."""
    profile = _owned_profile(request, profile_id)
    instruments = profile.instruments.filter(
        archived_at__isnull=True
    ).select_related("profile")
    archived_instruments = profile.instruments.filter(
        archived_at__isnull=False
    ).select_related("profile")
    return render(
        request,
        "tradefog/journal/profile_detail.html",
        {
            "profile": profile,
            "instruments": instruments,
            "archived_instruments": archived_instruments,
        },
    )


@login_required
@require_http_methods(["GET", "POST"])
def profile_edit(request: HttpRequest, profile_id: int) -> HttpResponse:
    """Edit an active profile owned by the authenticated user."""
    profile = _owned_profile(request, profile_id)
    form = TradingProfileForm(
        request.POST if request.method == "POST" else None,
        instance=profile,
    )
    if request.method == "POST" and form.is_valid():
        profile = cast(TradingProfile, form.save())
        return redirect("profile_detail", profile_id=profile.id)
    return render(
        request,
        "tradefog/journal/profile_form.html",
        {"form": form, "editing": True, "profile": profile},
    )


@login_required
@require_http_methods(["GET", "POST"])
def profile_archive(request: HttpRequest, profile_id: int) -> HttpResponse:
    """Confirm and archive an owned trading profile."""
    profile = _owned_profile(request, profile_id)
    if request.method == "POST":
        archive_profile(profile)
        return redirect("home")
    return render(
        request,
        "tradefog/journal/archive_confirm.html",
        {
            "object": profile,
            "object_kind": "profile",
            "cancel_url": profile.get_absolute_url(),
        },
    )


@login_required
@require_POST
def profile_restore(request: HttpRequest, profile_id: int) -> HttpResponse:
    """Restore an archived profile owned by the authenticated user."""
    profile = _owned_archived_profile(request, profile_id)
    restore_profile(profile)
    messages.success(request, _("Profile restored."))
    return redirect("profile_detail", profile_id=profile.id)


@login_required
@require_http_methods(["GET", "POST"])
def instrument_create(
    request: HttpRequest,
    profile_id: int,
) -> HttpResponse:
    """Add a venue-specific instrument to an owned profile."""
    profile = _owned_profile(request, profile_id)
    form = ProfileInstrumentForm(
        profile,
        request.POST if request.method == "POST" else None,
    )
    if request.method == "POST" and form.is_valid():
        instrument = cast(ProfileInstrument, form.save(commit=False))
        instrument.profile = profile
        instrument.save()
        return redirect("profile_detail", profile_id=profile.id)
    return render(
        request,
        "tradefog/journal/instrument_form.html",
        {"form": form, "editing": False, "profile": profile},
    )


@login_required
@require_http_methods(["GET", "POST"])
def instrument_edit(
    request: HttpRequest,
    profile_id: int,
    instrument_id: int,
) -> HttpResponse:
    """Edit an active instrument within an owned profile."""
    profile = _owned_profile(request, profile_id)
    instrument = _owned_instrument(profile, instrument_id)
    form = ProfileInstrumentForm(
        profile,
        request.POST if request.method == "POST" else None,
        instance=instrument,
    )
    if request.method == "POST" and form.is_valid():
        _ = cast(ProfileInstrument, form.save())
        return redirect("profile_detail", profile_id=profile.id)
    return render(
        request,
        "tradefog/journal/instrument_form.html",
        {
            "form": form,
            "editing": True,
            "profile": profile,
            "instrument": instrument,
        },
    )


@login_required
@require_http_methods(["GET", "POST"])
def instrument_archive(
    request: HttpRequest,
    profile_id: int,
    instrument_id: int,
) -> HttpResponse:
    """Confirm and archive an instrument within an owned profile."""
    profile = _owned_profile(request, profile_id)
    instrument = _owned_instrument(profile, instrument_id)
    if request.method == "POST":
        archive_instrument(instrument)
        return redirect("profile_detail", profile_id=profile.id)
    return render(
        request,
        "tradefog/journal/archive_confirm.html",
        {
            "object": instrument,
            "object_kind": "instrument",
            "cancel_url": profile.get_absolute_url(),
        },
    )


@login_required
@require_POST
def instrument_restore(
    request: HttpRequest,
    profile_id: int,
    instrument_id: int,
) -> HttpResponse:
    """Restore an archived instrument within an owned active profile."""
    profile = _owned_profile(request, profile_id)
    instrument = _owned_archived_instrument(profile, instrument_id)
    if restore_instrument(instrument):
        messages.success(request, _("Instrument restored."))
    else:
        messages.error(
            request,
            ACTIVE_MARKET_EXISTS
            + " "
            + _("Archive that instrument before restoring this one."),
        )
    return redirect("profile_detail", profile_id=profile.id)

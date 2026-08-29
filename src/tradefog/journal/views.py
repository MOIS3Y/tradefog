"""Owner-scoped HTTP views for profiles, capital, and instruments."""

from decimal import Decimal
from typing import cast

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.translation import gettext as _
from django.views.decorators.http import require_http_methods, require_POST

from tradefog.accounts.models import User
from tradefog.journal.forms import (
    CapitalOperationForm,
    ProfileInstrumentForm,
    TradingProfileForm,
)
from tradefog.journal.models import (
    ACTIVE_MARKET_EXISTS,
    CapitalOperation,
    ProfileInstrument,
    TradingProfile,
)
from tradefog.journal.services import (
    archive_instrument,
    archive_profile,
    create_capital_operation,
    delete_capital_operation,
    restore_instrument,
    restore_profile,
    sync_profile_status,
    update_capital_operation,
)


def _request_owner(request: HttpRequest) -> User:
    """Return the authenticated application user attached to a request."""
    return cast(User, request.user)


def _owned_profile(request: HttpRequest, profile_id: int) -> TradingProfile:
    """Resolve a non-archived profile within the ownership boundary."""
    return get_object_or_404(
        TradingProfile.objects.exclude(
            status=TradingProfile.Status.ARCHIVED.value
        ),
        id=profile_id,
        owner=_request_owner(request),
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
        status=TradingProfile.Status.ARCHIVED.value,
    )


def _owned_capital_operation(
    profile: TradingProfile,
    operation_id: int,
) -> CapitalOperation:
    """Resolve a capital operation belonging to the selected profile."""
    return get_object_or_404(
        CapitalOperation,
        id=operation_id,
        profile=profile,
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


def _profile_detail_context(
    profile: TradingProfile,
    *,
    deposit_form: CapitalOperationForm | None = None,
    withdrawal_form: CapitalOperationForm | None = None,
) -> dict[str, object]:
    """Build the configuration context shared by profile detail responses."""
    current_capital = profile.current_capital
    risk_base = max(profile.initial_capital, current_capital)
    reserved_risk = profile.reserved_risk
    worst_case_capital = current_capital - reserved_risk
    return {
        "profile": profile,
        "current_capital": current_capital,
        "risk_base": risk_base,
        "risk_amount": (
            risk_base * profile.risk_per_trade_percent / Decimal(100)
        ),
        "reserved_risk": reserved_risk,
        "worst_case_capital": worst_case_capital,
        "risk_capacity": worst_case_capital - profile.risk_stop_capital,
        "instruments": profile.instruments.filter(
            archived_at__isnull=True
        ).select_related("profile"),
        "archived_instruments": profile.instruments.filter(
            archived_at__isnull=False
        ).select_related("profile"),
        "capital_operations": profile.capital_operations.all(),
        "deposit_form": deposit_form
        or CapitalOperationForm(CapitalOperation.Type.DEPOSIT.value),
        "withdrawal_form": withdrawal_form
        or CapitalOperationForm(CapitalOperation.Type.WITHDRAWAL.value),
    }


def _render_profile_detail(
    request: HttpRequest,
    profile: TradingProfile,
    *,
    deposit_form: CapitalOperationForm | None = None,
    withdrawal_form: CapitalOperationForm | None = None,
) -> HttpResponse:
    """Render one profile with optional bound capital forms."""
    return render(
        request,
        "tradefog/journal/profile_detail.html",
        _profile_detail_context(
            profile,
            deposit_form=deposit_form,
            withdrawal_form=withdrawal_form,
        ),
    )


def _add_validation_errors(
    form: CapitalOperationForm,
    error: ValidationError,
) -> None:
    """Attach service validation failures to their form controls."""
    if hasattr(error, "message_dict"):
        for field_name, field_errors in error.message_dict.items():
            target = field_name if field_name in form.fields else None
            for field_error in field_errors:
                form.add_error(target, field_error)
        return
    for field_error in error.messages:
        form.add_error(None, field_error)


@login_required
def profile_overview(request: HttpRequest) -> HttpResponse:
    """List non-archived profiles owned by the authenticated user."""
    profiles = TradingProfile.objects.filter(owner=_request_owner(request))
    profiles = profiles.exclude(status=TradingProfile.Status.ARCHIVED.value)
    return render(
        request,
        "tradefog/journal/profile_overview.html",
        {
            "profiles": profiles,
            "archived_profile_count": TradingProfile.objects.filter(
                owner=_request_owner(request),
                status=TradingProfile.Status.ARCHIVED.value,
            ).count(),
        },
    )


@login_required
def archived_profile_overview(request: HttpRequest) -> HttpResponse:
    """List archived profiles owned by the authenticated user."""
    profiles = TradingProfile.objects.filter(
        owner=_request_owner(request),
        status=TradingProfile.Status.ARCHIVED.value,
    )
    return render(
        request,
        "tradefog/journal/archived_profile_overview.html",
        {"profiles": profiles},
    )


@login_required
@require_http_methods(["GET", "POST"])
def profile_create(request: HttpRequest) -> HttpResponse:
    """Create a manual trading profile for the authenticated user."""
    form = TradingProfileForm(
        request.POST if request.method == "POST" else None
    )
    if request.method == "POST" and form.is_valid():
        profile = cast(TradingProfile, form.save(commit=False))
        profile.owner = _request_owner(request)
        profile.save()
        _ = sync_profile_status(profile)
        return redirect("profile_detail", profile_id=profile.id)
    return render(
        request,
        "tradefog/journal/profile_form.html",
        {"form": form, "editing": False},
    )


@login_required
def profile_detail(request: HttpRequest, profile_id: int) -> HttpResponse:
    """Show one profile's capital policy and configured instruments."""
    return _render_profile_detail(request, _owned_profile(request, profile_id))


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
        _ = sync_profile_status(profile)
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
        return redirect("profile_overview")
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


def _create_capital_operation(
    request: HttpRequest,
    profile: TradingProfile,
    operation_type: str,
) -> HttpResponse:
    """Validate and apply one profile capital action."""
    form = CapitalOperationForm(operation_type, request.POST)
    if form.is_valid():
        try:
            _created_operation = create_capital_operation(
                profile,
                operation_type=operation_type,
                amount=cast(Decimal, form.cleaned_data["amount"]),
                note=cast(str, form.cleaned_data["note"]),
            )
        except ValidationError as error:
            _add_validation_errors(form, error)
        else:
            messages.success(request, _("Capital updated."))
            return redirect("profile_detail", profile_id=profile.id)
    if operation_type == CapitalOperation.Type.DEPOSIT.value:
        return _render_profile_detail(request, profile, deposit_form=form)
    return _render_profile_detail(request, profile, withdrawal_form=form)


@login_required
@require_POST
def capital_deposit(request: HttpRequest, profile_id: int) -> HttpResponse:
    """Allocate additional virtual capital to an owned profile."""
    return _create_capital_operation(
        request,
        _owned_profile(request, profile_id),
        CapitalOperation.Type.DEPOSIT.value,
    )


@login_required
@require_POST
def capital_withdraw(request: HttpRequest, profile_id: int) -> HttpResponse:
    """Remove virtual capital from an owned profile."""
    return _create_capital_operation(
        request,
        _owned_profile(request, profile_id),
        CapitalOperation.Type.WITHDRAWAL.value,
    )


@login_required
@require_http_methods(["GET", "POST"])
def capital_operation_edit(
    request: HttpRequest,
    profile_id: int,
    operation_id: int,
) -> HttpResponse:
    """Correct the amount or note of an owned capital operation."""
    profile = _owned_profile(request, profile_id)
    operation = _owned_capital_operation(profile, operation_id)
    operation_type = operation.operation_type
    form = CapitalOperationForm(
        operation_type,
        request.POST if request.method == "POST" else None,
        instance=operation,
    )
    if request.method == "POST" and form.is_valid():
        try:
            _updated_operation = update_capital_operation(
                operation,
                amount=cast(Decimal, form.cleaned_data["amount"]),
                note=cast(str, form.cleaned_data["note"]),
            )
        except ValidationError as error:
            _add_validation_errors(form, error)
        else:
            messages.success(request, _("Capital operation updated."))
            return redirect("profile_detail", profile_id=profile.id)
    return render(
        request,
        "tradefog/journal/capital_operation_form.html",
        {"form": form, "profile": profile, "operation": operation},
    )


@login_required
@require_http_methods(["GET", "POST"])
def capital_operation_delete(
    request: HttpRequest,
    profile_id: int,
    operation_id: int,
) -> HttpResponse:
    """Confirm and delete an erroneous owned capital operation."""
    profile = _owned_profile(request, profile_id)
    operation = _owned_capital_operation(profile, operation_id)
    if request.method == "POST":
        try:
            delete_capital_operation(operation)
        except ValidationError as error:
            messages.error(request, " ".join(error.messages))
        else:
            messages.success(request, _("Capital operation deleted."))
        return redirect("profile_detail", profile_id=profile.id)
    return render(
        request,
        "tradefog/journal/capital_operation_delete.html",
        {"profile": profile, "operation": operation},
    )


@login_required
@require_http_methods(["GET", "POST"])
def instrument_create(
    request: HttpRequest,
    profile_id: int,
) -> HttpResponse:
    """Add a provider-specific instrument to an owned profile."""
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

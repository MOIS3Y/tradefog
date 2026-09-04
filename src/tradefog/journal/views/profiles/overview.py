"""Profile overview: owner-scoped card grid with modal create and delete.

The profile collection is naturally small, so it renders as a responsive
card grid rather than a paginated table. Each card shows the profile name,
its venue, wallet-asset and strategy counts, and an archived badge when
applicable.
"""

from __future__ import annotations

import json
from typing import Any

from django.contrib.auth.decorators import login_required
from django.db import IntegrityError, transaction
from django.db.models import Count
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, render
from django.utils.translation import gettext_lazy as _

from tradefog.journal.forms import TradingProfileForm
from tradefog.journal.models import TradingProfile, Wallet


@login_required
def profile_overview(request: HttpRequest) -> HttpResponse:
    """List the current user's trading profiles as a card grid."""
    return render(
        request,
        "tradefog/profiles/overview.html",
        _card_context(request),
    )


@login_required
def profile_create(request: HttpRequest) -> HttpResponse:
    """Render the create form fragment or accept a new profile.

    A GET request supplies the modal form. A valid POST creates the
    profile with its one-to-one wallet in a single transaction and
    returns the refreshed card grid out of band; an invalid POST
    returns the form with field errors and a 422 status so the modal
    stays open.
    """
    form = TradingProfileForm(request.POST or None)
    if request.method == "POST":
        if form.is_valid():
            try:
                with transaction.atomic():
                    profile = form.save(commit=False)
                    profile.owner = request.user
                    profile.save()
                    Wallet.objects.create(  # pyright: ignore[reportUnusedCallResult]
                        profile=profile
                    )
            except IntegrityError:
                form.add_error(
                    "name",
                    _("A profile with this name already exists."),
                )
                return render(
                    request,
                    "tradefog/profiles/partials/profile_create_form.html",
                    {"form": form},
                    status=422,
                )
            context = _card_context(request, swap_oob=True)
            response = render(
                request,
                "tradefog/profiles/partials/profile_cards.html",
                context,
            )
            response["HX-Trigger"] = json.dumps(
                {
                    "tradefog:toast": {
                        "message": str(_("Profile created.")),
                        "kind": "success",
                    },
                    "tradefog:close-modal": {
                        "id": "profile-create-modal",
                    },
                }
            )
            return response
        return render(
            request,
            "tradefog/profiles/partials/profile_create_form.html",
            {"form": form},
            status=422,
        )
    return render(
        request,
        "tradefog/profiles/partials/profile_create_form.html",
        {"form": form},
    )


@login_required
def profile_archive(
    request: HttpRequest, pk: int
) -> HttpResponse:
    """Render an archive confirmation or archive a profile.

    A GET request supplies the confirmation form. A POST archives
    the profile without touching its wallet, strategies, or trades
    and returns the refreshed card grid out of band.
    """
    profile = get_object_or_404(
        TradingProfile, pk=pk, owner=request.user
    )
    if request.method == "POST":
        if profile.archived:
            return _inactive_action_response("profile-archive-modal")
        profile.archived = True
        profile.save(update_fields=["archived"])
        return _cards_response(
            request,
            message=_("Profile archived."),
            close_modal="profile-archive-modal",
        )
    return render(
        request,
        "tradefog/profiles/partials/profile_archive_confirm.html",
        {"profile": profile},
    )


@login_required
def profile_restore(
    request: HttpRequest, pk: int
) -> HttpResponse:
    """Restore an archived profile so it is active again.

    A POST-only action: restores the profile without confirmation
    and returns the refreshed card grid out of band.
    """
    if request.method != "POST":
        return _cards_response(
            request,
            message=_("Profile not found."),
            kind="danger",
        )
    profile = get_object_or_404(
        TradingProfile, pk=pk, owner=request.user
    )
    if not profile.archived:
        return _inactive_action_response("profile-restore")
    profile.archived = False
    profile.save(update_fields=["archived"])
    return _cards_response(
        request,
        message=_("Profile restored."),
    )


@login_required
def profile_delete(
    request: HttpRequest, pk: int
) -> HttpResponse:
    """Render a delete confirmation or permanently remove a profile.

    A GET request supplies the confirmation form. A POST removes the
    profile (cascading wallet, strategies, and trades) and returns the
    refreshed card grid out of band. Only archived profiles can be
    deleted permanently; active profiles must be archived first.
    """
    profile = get_object_or_404(
        TradingProfile, pk=pk, owner=request.user
    )
    if request.method == "POST":
        if not profile.archived:
            message = _(
                "Archive the profile before deleting it permanently."
            )
            response = HttpResponse(status=409)
            response["HX-Trigger"] = json.dumps(
                {
                    "tradefog:toast": {
                        "message": str(message),
                        "kind": "danger",
                    },
                    "tradefog:close-modal": {
                        "id": "profile-delete-modal",
                    },
                }
            )
            return response
        profile.delete()  # pyright: ignore[reportUnusedCallResult]
        return _cards_response(
            request,
            message=_("Profile deleted."),
            close_modal="profile-delete-modal",
        )
    return render(
        request,
        "tradefog/profiles/partials/profile_delete_confirm.html",
        {"profile": profile},
    )


def _cards_response(
    request: HttpRequest,
    *,
    message: str,
    kind: str = "success",
    close_modal: str | None = None,
) -> HttpResponse:
    """Render the refreshed card grid out of band with a toast."""
    context = _card_context(request, swap_oob=True)
    response = render(
        request,
        "tradefog/profiles/partials/profile_cards.html",
        context,
    )
    trigger: dict[str, object] = {
        "tradefog:toast": {
            "message": str(message),
            "kind": kind,
        },
    }
    if close_modal is not None:
        trigger["tradefog:close-modal"] = {"id": close_modal}
    response["HX-Trigger"] = json.dumps(trigger)
    return response


def _inactive_action_response(close_modal: str) -> HttpResponse:
    """Refuse an archive or restore action that is already the state."""
    response = HttpResponse(status=409)
    response["HX-Trigger"] = json.dumps(
        {
            "tradefog:toast": {
                "message": str(_("The profile already has this status.")),
                "kind": "danger",
            },
            "tradefog:close-modal": {"id": close_modal},
        }
    )
    return response


def _card_context(
    request: HttpRequest,
    *,
    swap_oob: bool = False,
) -> dict[str, Any]:
    """Build the card-grid context for the current user.

    Profiles split into an active grid and an archive section that is
    shown only when at least one profile is archived.
    """
    profiles = (
        TradingProfile.objects.filter(owner=request.user)
        .select_related("venue")
        .annotate(
            strategy_count=Count("strategies", distinct=True),
            wallet_asset_count=Count(
                "wallet__assets", distinct=True
            ),
        )
    )
    active_profiles = profiles.filter(archived=False).order_by("name")
    archived_profiles = profiles.filter(archived=True).order_by("name")
    return {
        "active_profiles": active_profiles,
        "archived_profiles": archived_profiles,
        "has_archived": archived_profiles.exists(),
        "swap_oob": swap_oob,
    }

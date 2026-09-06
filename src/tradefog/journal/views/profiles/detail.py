"""Profile detail page with card-header tabs.

The detail page follows the venue detail pattern: a heading with a back
action and a card with four tabs — Overview, Wallet, Strategies, and
Settings. The Overview tab shows a static summary of the profile; the
remaining tabs are empty until their dedicated stages land.
"""

import json

from django.contrib.auth.decorators import login_required
from django.db import IntegrityError, transaction
from django.db.models import Count
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, render
from django.template.loader import render_to_string
from django.utils.translation import gettext_lazy as _

from tradefog.journal.forms import TradingProfileSettingsForm
from tradefog.journal.models import TradingProfile
from tradefog.journal.views.profiles.common import profile_overview_html
from tradefog.journal.views.profiles.strategies import strategies_context
from tradefog.journal.views.profiles.wallet import wallet_context


@login_required
def profile_detail(request: HttpRequest, pk: int) -> HttpResponse:
    """Render one owner-scoped profile with its tabbed sections."""
    profile = get_object_or_404(TradingProfile, pk=pk, owner=request.user)
    profile = (
        TradingProfile.objects.filter(pk=profile.pk, owner=request.user)
        .select_related("venue")
        .annotate(
            strategy_count=Count("strategies", distinct=True),
            wallet_asset_count=Count("wallet__assets", distinct=True),
            trade_count=Count("strategies__trades", distinct=True),
        )
        .get()
    )
    if request.headers.get("HX-Request") == "true":
        if "op_sort" in request.GET or "op_page" in request.GET:
            return render(
                request,
                "tradefog/profiles/partials/wallet_content.html",
                {"section": wallet_context(request, profile)},
            )
        if "st_sort" in request.GET or "st_page" in request.GET:
            return render(
                request,
                "tradefog/profiles/partials/strategies_content.html",
                {"section": strategies_context(request, profile)},
            )
    return render(
        request,
        "tradefog/profiles/profile_detail.html",
        {
            "profile": profile,
            "form": TradingProfileSettingsForm(instance=profile),
            "wallet": wallet_context(request, profile),
            "strategies": strategies_context(request, profile),
        },
    )


@login_required
def profile_edit(request: HttpRequest, pk: int) -> HttpResponse:
    """Render the settings form fragment or update an owner-scoped profile.

    The profile's name and description are edited on the profile detail page's
    Settings tab. A valid POST saves the profile and returns the refreshed
    settings form plus an out-of-band ``#profile-heading`` fragment and
    an out-of-band ``#profile-overview-content`` fragment so the overview and
    page title follow a renamed profile; an invalid POST returns the form with
    field errors and a 422 status.
    """
    profile = get_object_or_404(TradingProfile, pk=pk, owner=request.user)
    form = TradingProfileSettingsForm(request.POST or None, instance=profile)
    if request.method == "POST":
        if form.is_valid():
            try:
                with transaction.atomic():
                    form.save()
            except IntegrityError:
                form.add_error(
                    "name", _("A profile with this name already exists.")
                )
                return render(
                    request,
                    "tradefog/profiles/partials/profile_settings_form.html",
                    {"form": form, "profile": profile},
                    status=422,
                )
            settings_html = render_to_string(
                "tradefog/profiles/partials/profile_settings_form.html",
                {"form": form, "profile": profile},
                request=request,
            )
            heading_html = render_to_string(
                "tradefog/profiles/partials/profile_heading.html",
                {"profile": profile, "swap_oob": True},
                request=request,
            )
            overview_html = profile_overview_html(request, profile)
            response = HttpResponse(
                settings_html + heading_html + overview_html
            )
            response["HX-Trigger"] = json.dumps(
                {
                    "tradefog:toast": {
                        "message": str(_("Profile updated.")),
                        "kind": "success",
                    }
                }
            )
            return response
        return render(
            request,
            "tradefog/profiles/partials/profile_settings_form.html",
            {"form": form, "profile": profile},
            status=422,
        )
    return render(
        request,
        "tradefog/profiles/partials/profile_settings_form.html",
        {"form": form, "profile": profile},
    )

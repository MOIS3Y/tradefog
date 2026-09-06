"""Shared helpers for profile tab views."""

from __future__ import annotations

from django.db.models import Count
from django.http import HttpRequest
from django.template.loader import render_to_string

from tradefog.journal.models import TradingProfile


def profile_overview_html(
    request: HttpRequest, profile: TradingProfile
) -> str:
    """Render the profile overview tab fragment out of band."""
    annotated = (
        TradingProfile.objects.filter(pk=profile.pk, owner=request.user)
        .select_related("venue")
        .annotate(
            strategy_count=Count("strategies", distinct=True),
            wallet_asset_count=Count("wallet__assets", distinct=True),
            trade_count=Count("strategies__trades", distinct=True),
        )
        .get()
    )
    return render_to_string(
        "tradefog/profiles/partials/profile_overview_tab.html",
        {"profile": annotated, "swap_oob": True},
        request=request,
    )

"""Profile detail page with card-header tabs.

The detail page follows the venue detail pattern: a heading with a back
action and a card with four tabs — Overview, Wallet, Strategies, and
Settings. The Overview tab shows a static summary of the profile; the
remaining tabs are empty until their dedicated stages land.
"""

from __future__ import annotations

from typing import Any

from django.contrib.auth.decorators import login_required
from django.db.models import Count
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, render

from tradefog.journal.models import TradingProfile


@login_required
def profile_detail(
    request: HttpRequest, pk: int
) -> HttpResponse:
    """Render one owner-scoped profile with its tabbed sections."""
    profile = get_object_or_404(
        TradingProfile, pk=pk, owner=request.user
    )
    profile = (
        TradingProfile.objects.filter(pk=profile.pk, owner=request.user)
        .select_related("venue")
        .annotate(
            strategy_count=Count("strategies", distinct=True),
            wallet_asset_count=Count(
                "wallet__assets", distinct=True
            ),
            trade_count=Count("strategies__trades", distinct=True),
        )
        .get()
    )
    return render(
        request,
        "tradefog/profiles/profile_detail.html",
        _detail_context(profile),
    )


def _detail_context(profile: TradingProfile) -> dict[str, Any]:
    """Build the detail-page context for one profile."""
    return {
        "profile": profile,
    }
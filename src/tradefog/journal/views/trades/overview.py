"""Trade journal overview and listing views."""

from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render

from tradefog.journal.models import Trade, TradingProfile


@login_required
def trade_overview(request: HttpRequest) -> HttpResponse:
    """Render the journal trades list/overview page."""
    trades = (
        Trade.objects.filter(profile__owner=request.user)
        .select_related(
            "profile",
            "strategy",
            "venue_instrument__venue",
            "venue_instrument__pair__base",
            "venue_instrument__pair__quote",
        )
        .order_by("-trade_date", "-id")
    )
    has_active_profiles = TradingProfile.objects.filter(
        owner=request.user, is_archived=False
    ).exists()
    return render(
        request,
        "tradefog/trades/overview.html",
        {
            "trades": trades,
            "has_active_profiles": has_active_profiles,
        },
    )

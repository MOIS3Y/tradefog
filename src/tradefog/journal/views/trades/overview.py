"""Trade journal overview, filtering, and listing views."""

from __future__ import annotations

import json
from typing import Any

from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, render
from django.utils.translation import gettext_lazy as _

from tradefog.journal.models import Trade, TradingProfile, TradingStrategy
from tradefog.journal.models.enums import Direction, TradeStatus
from tradefog.journal.views.catalog.common import (
    SortColumn,
    build_results_context,
)

SORT_COLUMNS: tuple[SortColumn, ...] = (
    ("date", _("Date")),
    ("market", _("Market")),
    ("direction", _("Direction")),
    ("status", _("Status")),
    ("pnl", _("Realized P&L")),
)

DEFAULT_SORT = "-date"
PAGE_SIZE = 15


def _get_overview_context(
    request: HttpRequest, *, swap_oob: bool = False
) -> dict[str, Any]:
    search = request.GET.get("q", "").strip()
    status_filter = request.GET.get("status", "").strip()
    profile_filter = request.GET.get("profile", "").strip()
    strategy_filter = request.GET.get("strategy", "").strip()
    direction_filter = request.GET.get("direction", "").strip()
    current_sort = request.GET.get("sort", DEFAULT_SORT)

    queryset = (
        Trade.objects.filter(profile__owner=request.user)
        .select_related(
            "profile",
            "strategy",
            "venue_instrument__venue",
            "venue_instrument__pair__base",
            "venue_instrument__pair__quote",
            "snapshot",
        )
        .prefetch_related("attachments")
    )

    filters_active = False

    if search:
        filters_active = True
        queryset = queryset.filter(
            Q(venue_instrument__pair__base__symbol__icontains=search)
            | Q(venue_instrument__pair__quote__symbol__icontains=search)
            | Q(venue_instrument__exec_symbol__icontains=search)
            | Q(strategy__name__icontains=search)
            | Q(profile__name__icontains=search)
            | Q(description_markdown__icontains=search)
        )

    if status_filter:
        filters_active = True
        queryset = queryset.filter(status=status_filter)

    if profile_filter:
        filters_active = True
        queryset = queryset.filter(profile_id=profile_filter)

    if strategy_filter:
        filters_active = True
        queryset = queryset.filter(strategy_id=strategy_filter)

    if direction_filter:
        filters_active = True
        queryset = queryset.filter(direction=direction_filter)

    # Sorting
    if current_sort == "date":
        queryset = queryset.order_by("trade_date", "id")
    elif current_sort == "-date":
        queryset = queryset.order_by("-trade_date", "-id")
    elif current_sort == "market":
        queryset = queryset.order_by(
            "venue_instrument__pair__base__symbol",
            "venue_instrument__pair__quote__symbol",
            "-trade_date",
        )
    elif current_sort == "-market":
        queryset = queryset.order_by(
            "-venue_instrument__pair__base__symbol",
            "-venue_instrument__pair__quote__symbol",
            "-trade_date",
        )
    elif current_sort == "direction":
        queryset = queryset.order_by("direction", "-trade_date")
    elif current_sort == "-direction":
        queryset = queryset.order_by("-direction", "-trade_date")
    elif current_sort == "status":
        queryset = queryset.order_by("status", "-trade_date")
    elif current_sort == "-status":
        queryset = queryset.order_by("-status", "-trade_date")
    elif current_sort == "pnl":
        queryset = queryset.order_by("realized_pnl", "-trade_date")
    elif current_sort == "-pnl":
        queryset = queryset.order_by("-realized_pnl", "-trade_date")
    else:
        current_sort = DEFAULT_SORT
        queryset = queryset.order_by("-trade_date", "-id")

    results_context = build_results_context(
        request,
        queryset=queryset,
        page_size=PAGE_SIZE,
        current_sort=current_sort,
        columns=SORT_COLUMNS,
        filters_active=filters_active,
        can_manage=True,
        results_key="trades",
    )

    has_active_profiles = TradingProfile.objects.filter(
        owner=request.user, is_archived=False
    ).exists()

    profiles = list(
        TradingProfile.objects.filter(
            owner=request.user, is_archived=False
        ).order_by("name")
    )
    strategies = list(
        TradingStrategy.objects.filter(
            profile__owner=request.user, is_archived=False
        )
        .select_related("profile")
        .order_by("name")
    )

    return {
        **results_context,
        "search": search,
        "status_filter": status_filter,
        "profile_filter": profile_filter,
        "strategy_filter": strategy_filter,
        "direction_filter": direction_filter,
        "status_choices": TradeStatus.choices,
        "direction_choices": Direction.choices,
        "profiles": profiles,
        "strategies": strategies,
        "has_active_profiles": has_active_profiles,
        "swap_oob": swap_oob,
    }


@login_required
def trade_overview(request: HttpRequest) -> HttpResponse:
    """Render the journal trades list/overview page with filters and sorting."""
    context = _get_overview_context(request)

    if request.headers.get("HX-Request") and not request.headers.get(
        "HX-Boosted"
    ):
        return render(
            request,
            "tradefog/trades/partials/trade_results.html",
            context,
        )

    return render(request, "tradefog/trades/overview.html", context)


@login_required
def trade_delete(request: HttpRequest, pk: int) -> HttpResponse:
    """Render a delete confirmation or remove a draft trade."""
    trade = get_object_or_404(
        Trade.objects.select_related("profile", "venue_instrument__pair"),
        pk=pk,
        profile__owner=request.user,
    )
    if request.method == "POST":
        if trade.status != TradeStatus.DRAFT.value:
            response = HttpResponse(status=409)
            response["HX-Trigger"] = json.dumps(
                {
                    "tradefog:toast": {
                        "message": str(_("Only trade drafts can be deleted.")),
                        "kind": "danger",
                    },
                    "tradefog:close-modal": {"id": "trade-delete-modal"},
                }
            )
            return response

        trade.delete()
        context = _get_overview_context(request, swap_oob=True)
        response = render(
            request,
            "tradefog/trades/partials/trade_results.html",
            context,
        )
        response["HX-Trigger"] = json.dumps(
            {
                "tradefog:toast": {
                    "message": str(_("Trade draft deleted.")),
                    "kind": "success",
                },
                "tradefog:close-modal": {"id": "trade-delete-modal"},
            }
        )
        return response

    return render(
        request,
        "tradefog/trades/partials/trade_delete_form.html",
        {"trade": trade},
    )

"""Owner-scoped strategy views for one profile.

The Strategies tab renders a sortable, paginated table of the profile's
strategies. Strategies are created and edited through modals and archived
(rather than deleted) so they stop appearing in trade selection. Capital
allocations are managed inline inside a strategy detail modal.
"""

from __future__ import annotations

import json
from typing import Any

from django.contrib.auth.decorators import login_required
from django.db.models import Count
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, render
from django.template.loader import render_to_string
from django.utils.translation import gettext_lazy as _

from tradefog.journal.forms import (
    StrategyCapitalForm,
    TradingStrategyForm,
)
from tradefog.journal.models import (
    StrategyCapital,
    TradingProfile,
    TradingStrategy,
)
from tradefog.journal.services import (
    settlement_asset_ids,
    strategy_has_active_trades_in_asset,
)
from tradefog.journal.views.catalog.common import build_results_context
from tradefog.journal.views.profiles.common import profile_overview_html

STRATEGY_PAGE_SIZE = 10

STRATEGY_SORT_FIELDS = {
    "name": ("name", "id"),
    "-name": ("-name", "-id"),
    "risk_percent": ("risk_percent", "id"),
    "-risk_percent": ("-risk_percent", "-id"),
    "reward_multiple": ("reward_multiple", "id"),
    "-reward_multiple": ("-reward_multiple", "-id"),
    "status": ("is_archived", "name", "id"),
    "-status": ("-is_archived", "-name", "-id"),
    "allocations": ("allocation_count", "name", "id"),
    "-allocations": ("-allocation_count", "-name", "-id"),
}

STRATEGY_SORT_COLUMNS = (
    ("name", _("Name")),
    ("risk_percent", _("Risk %")),
    ("reward_multiple", _("Reward")),
    ("status", _("Status")),
    ("allocations", _("Allocations")),
)


@login_required
def strategy_create(request: HttpRequest, pk: int) -> HttpResponse:
    """Render a create form fragment or accept a new strategy."""
    profile = _get_profile(request, pk)
    if profile.is_archived:
        return _archived_response("strategy-create-modal")
    form = TradingStrategyForm(request.POST or None)
    if request.method == "POST":
        if form.is_valid():
            strategy = form.save(commit=False)
            strategy.profile = profile
            strategy.save()
            return _strategies_response(
                request,
                profile,
                message=_("Strategy created."),
                close_modal="strategy-create-modal",
            )
        return render(
            request,
            "tradefog/profiles/partials/strategy_create_form.html",
            {"form": form, "profile": profile},
            status=422,
        )
    return render(
        request,
        "tradefog/profiles/partials/strategy_create_form.html",
        {"form": form, "profile": profile},
    )


@login_required
def strategy_edit(
    request: HttpRequest, pk: int, strategy_pk: int
) -> HttpResponse:
    """Render an edit form fragment or update a strategy."""
    profile = _get_profile(request, pk)
    if profile.is_archived:
        return _archived_response("strategy-edit-modal")
    strategy = _strategy(request, pk, strategy_pk)
    form = TradingStrategyForm(request.POST or None, instance=strategy)
    if request.method == "POST":
        if form.is_valid():
            strategy.name = form.cleaned_data["name"]
            strategy.description = form.cleaned_data["description"]
            strategy.save(update_fields=["name", "description"])
            return _strategies_response(
                request,
                profile,
                message=_("Strategy updated."),
                close_modal="strategy-edit-modal",
            )
        return render(
            request,
            "tradefog/profiles/partials/strategy_edit_form.html",
            {"form": form, "profile": profile, "strategy": strategy},
            status=422,
        )
    return render(
        request,
        "tradefog/profiles/partials/strategy_edit_form.html",
        {"form": form, "profile": profile, "strategy": strategy},
    )


@login_required
def strategy_archive(
    request: HttpRequest, pk: int, strategy_pk: int
) -> HttpResponse:
    """Archive a strategy so it stops appearing in trade selection."""
    profile = _get_profile(request, pk)
    if profile.is_archived:
        return _archived_response("strategy-archive-modal")
    strategy = _strategy(request, pk, strategy_pk)
    if request.method == "GET":
        return render(
            request,
            "tradefog/profiles/partials/strategy_archive_confirm.html",
            {"profile": profile, "strategy": strategy},
        )
    if not strategy.is_archived:
        strategy.is_archived = True
        strategy.save(update_fields=["is_archived"])
        return _strategies_response(
            request,
            profile,
            message=_("Strategy archived."),
            close_modal="strategy-archive-modal",
        )
    return _inactive_action_response("strategy-archive-modal")


@login_required
def strategy_restore(
    request: HttpRequest, pk: int, strategy_pk: int
) -> HttpResponse:
    """Restore an archived strategy to active status."""
    profile = _get_profile(request, pk)
    if profile.is_archived:
        return _archived_response("strategy-restore")
    strategy = _strategy(request, pk, strategy_pk)
    if strategy.is_archived:
        strategy.is_archived = False
        strategy.save(update_fields=["is_archived"])
        return _strategies_response(
            request,
            profile,
            message=_("Strategy restored."),
        )
    return _inactive_action_response("strategy-restore")


@login_required
def strategy_detail(
    request: HttpRequest, pk: int, strategy_pk: int
) -> HttpResponse:
    """Return the strategy detail modal content with its allocations."""
    profile = _get_profile(request, pk)
    strategy = _strategy(request, pk, strategy_pk)
    return render(
        request,
        "tradefog/profiles/partials/strategy_detail.html",
        _detail_context(profile, strategy),
    )


@login_required
def strategy_capital_add(
    request: HttpRequest, pk: int, strategy_pk: int
) -> HttpResponse:
    """Add a capital allocation to a strategy."""
    profile = _get_profile(request, pk)
    if profile.is_archived:
        return _archived_response("strategy-detail-body")
    strategy = _strategy(request, pk, strategy_pk)
    form = StrategyCapitalForm(request.POST or None, strategy=strategy)
    if request.method == "POST":
        if form.is_valid():
            form.save()  # pyright: ignore[reportUnusedCallResult]
            return _detail_response(
                request,
                profile,
                strategy,
                message=_("Allocation added."),
            )
        return render(
            request,
            "tradefog/profiles/partials/strategy_detail.html",
            {
                **_detail_context(profile, strategy),
                "capital_form": form,
            },
            status=422,
        )
    return render(
        request,
        "tradefog/profiles/partials/strategy_detail.html",
        {
            **_detail_context(profile, strategy),
            "capital_form": form,
        },
    )


@login_required
def strategy_capital_archive(
    request: HttpRequest, pk: int, strategy_pk: int, capital_pk: int
) -> HttpResponse:
    """Archive a capital allocation so its asset stops participating.

    Archiving is refused while any unfinished trade settles in the asset, so a
    draft or open trade cannot inherit a frozen-then-removed risk base. The
    allocation keeps its slot; its fixed capital can never be replaced.
    """
    profile = _get_profile(request, pk)
    if profile.is_archived:
        return _archived_response("strategy-detail-body")
    strategy = _strategy(request, pk, strategy_pk)
    capital = _capital(request, pk, strategy_pk, capital_pk)
    if capital.is_archived:
        return _inactive_action_response("strategy-detail-body")
    asset_id = capital.wallet_asset.venue_wallet_asset.asset_id
    if strategy_has_active_trades_in_asset(strategy, asset_id):
        return _active_trades_response()
    capital.is_archived = True
    capital.save(update_fields=["is_archived"])
    return _detail_response(
        request,
        profile,
        strategy,
        message=_("Allocation archived."),
    )


@login_required
def strategy_capital_restore(
    request: HttpRequest, pk: int, strategy_pk: int, capital_pk: int
) -> HttpResponse:
    """Restore an archived capital allocation to active participation."""
    profile = _get_profile(request, pk)
    if profile.is_archived:
        return _archived_response("strategy-detail-body")
    strategy = _strategy(request, pk, strategy_pk)
    capital = _capital(request, pk, strategy_pk, capital_pk)
    if not capital.is_archived:
        return _inactive_action_response("strategy-detail-body")
    capital.is_archived = False
    capital.save(update_fields=["is_archived"])
    return _detail_response(
        request,
        profile,
        strategy,
        message=_("Allocation restored."),
    )


def strategies_context(
    request: HttpRequest,
    profile: TradingProfile,
    *,
    swap_oob: bool = False,
) -> dict[str, Any]:
    """Build the Strategies tab context for one profile."""
    queryset = TradingStrategy.objects.filter(profile=profile).annotate(
        allocation_count=Count("capitals", distinct=True)
    )
    requested_sort = request.GET.get("st_sort", "name")
    current_sort = (
        requested_sort if requested_sort in STRATEGY_SORT_FIELDS else "name"
    )
    section = build_results_context(
        request,
        queryset=queryset.order_by(*STRATEGY_SORT_FIELDS[current_sort]),
        page_size=STRATEGY_PAGE_SIZE,
        current_sort=current_sort,
        columns=STRATEGY_SORT_COLUMNS,
        filters_active=False,
        can_manage=not profile.is_archived,
        results_key="strategies",
        swap_oob=False,
        sort_parameter="st_sort",
        page_parameter="st_page",
    )
    section.update(
        {
            "profile": profile,
            "swap_oob": swap_oob,
        }
    )
    return section


def _detail_context(
    profile: TradingProfile, strategy: TradingStrategy
) -> dict[str, Any]:
    """Build the strategy detail modal context."""
    allocations = strategy.capitals.select_related(
        "wallet_asset__venue_wallet_asset__asset"
    ).order_by("wallet_asset__venue_wallet_asset__asset__symbol")
    capital_form = StrategyCapitalForm(strategy=strategy)

    settlement_ids = settlement_asset_ids(profile.venue)
    wallet_assets = profile.wallet.assets.filter(
        is_archived=False
    ).select_related("venue_wallet_asset__asset")

    unsettled_assets = [
        wa.venue_wallet_asset.asset.symbol
        for wa in wallet_assets
        if wa.venue_wallet_asset.asset_id not in settlement_ids
    ]
    has_wallet_assets = wallet_assets.exists()

    return {
        "profile": profile,
        "strategy": strategy,
        "allocations": allocations,
        "capital_form": capital_form,
        "has_wallet_assets": has_wallet_assets,
        "unsettled_assets": unsettled_assets,
    }


def _detail_response(
    request: HttpRequest,
    profile: TradingProfile,
    strategy: TradingStrategy,
    *,
    message: str,
) -> HttpResponse:
    """Render refreshed modal detail, strategies table, and overview tab."""
    detail_html = render_to_string(
        "tradefog/profiles/partials/strategy_detail.html",
        _detail_context(profile, strategy),
        request=request,
    )
    content_html = render_to_string(
        "tradefog/profiles/partials/strategies_content.html",
        {"section": strategies_context(request, profile, swap_oob=True)},
        request=request,
    )
    overview_html = profile_overview_html(request, profile)
    response = HttpResponse(detail_html + content_html + overview_html)
    response["HX-Trigger"] = json.dumps(
        {
            "tradefog:toast": {
                "message": str(message),
                "kind": "success",
            }
        }
    )
    return response


def _strategies_response(
    request: HttpRequest,
    profile: TradingProfile,
    *,
    message: str,
    close_modal: str | None = None,
) -> HttpResponse:
    """Render refreshed Strategies and Overview tabs out of band with a toast."""
    content_html = render_to_string(
        "tradefog/profiles/partials/strategies_content.html",
        {"section": strategies_context(request, profile, swap_oob=True)},
        request=request,
    )
    overview_html = profile_overview_html(request, profile)
    response = HttpResponse(content_html + overview_html)
    trigger: dict[str, object] = {
        "tradefog:toast": {
            "message": str(message),
            "kind": "success",
        }
    }
    if close_modal is not None:
        trigger["tradefog:close-modal"] = {"id": close_modal}
    response["HX-Trigger"] = json.dumps(trigger)
    return response


def _get_profile(request: HttpRequest, pk: int) -> TradingProfile:
    """Return the current user's profile or raise a 404."""
    return get_object_or_404(TradingProfile, pk=pk, owner=request.user)


def _strategy(
    request: HttpRequest, pk: int, strategy_pk: int
) -> TradingStrategy:
    """Return an owner-scoped strategy or raise a 404."""
    return get_object_or_404(
        TradingStrategy,
        pk=strategy_pk,
        profile__owner=request.user,
        profile__pk=pk,
    )


def _capital(
    request: HttpRequest, pk: int, strategy_pk: int, capital_pk: int
) -> StrategyCapital:
    """Return an owner-scoped allocation or raise a 404."""
    return get_object_or_404(
        StrategyCapital,
        pk=capital_pk,
        strategy=_strategy(request, pk, strategy_pk),
    )


def _archived_response(close_modal: str) -> HttpResponse:
    """Refuse a strategy mutation on an archived profile."""
    response = HttpResponse(status=409)
    response["HX-Trigger"] = json.dumps(
        {
            "tradefog:toast": {
                "message": str(
                    _("Restore the profile to manage its strategies.")
                ),
                "kind": "danger",
            },
            "tradefog:close-modal": {"id": close_modal},
        }
    )
    return response


def _inactive_action_response(close_modal: str) -> HttpResponse:
    """Refuse an archive or restore that is already the strategy state."""
    response = HttpResponse(status=409)
    response["HX-Trigger"] = json.dumps(
        {
            "tradefog:toast": {
                "message": str(_("The strategy already has this status.")),
                "kind": "danger",
            },
            "tradefog:close-modal": {"id": close_modal},
        }
    )
    return response


def _active_trades_response() -> HttpResponse:
    """Refuse archiving an allocation that still backs unfinished trades."""
    response = HttpResponse(status=409)
    response["HX-Trigger"] = json.dumps(
        {
            "tradefog:toast": {
                "message": str(
                    _(
                        "Cancel or wait for open trades to close before "
                        + "archiving this allocation."
                    )
                ),
                "kind": "danger",
            },
        }
    )
    return response

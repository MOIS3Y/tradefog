"""Views for shared venues, their wallet assets, and the venue detail page.

The venue collection is deliberately small, so it renders as a responsive
card grid rather than a paginated table. The venue detail page hosts two
independent table sections — the venue's wallet-capable assets and its
executable instruments — each with its own prefixed query parameters so they
filter, sort, and paginate without resetting one another.

Every authenticated user reads the catalog. Staff members create, edit, and
remove records; regular user queries never write to the shared catalog.
"""

from __future__ import annotations

import json
from typing import Any, TypedDict

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import IntegrityError
from django.db.models import Count, Q, QuerySet
from django.db.models.deletion import ProtectedError
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, render
from django.template.loader import render_to_string
from django.utils.translation import gettext_lazy as _

from tradefog.journal.forms import VenueForm, VenueWalletAssetForm
from tradefog.journal.models import Venue, VenueWalletAsset
from tradefog.journal.models.enums import AssetType, ProductKind
from tradefog.journal.views.catalog.common import build_results_context

WALLET_ASSET_PAGE_SIZE = 10

WALLET_ASSET_SORT_FIELDS = {
    "symbol": ("asset__symbol", "id"),
    "-symbol": ("-asset__symbol", "-id"),
    "name": ("asset__name", "asset__symbol", "id"),
    "-name": ("-asset__name", "-asset__symbol", "-id"),
    "asset_type": ("asset__asset_type", "asset__symbol", "id"),
    "-asset_type": ("-asset__asset_type", "-asset__symbol", "-id"),
}

WALLET_ASSET_SORT_COLUMNS = (
    ("symbol", _("Asset")),
    ("name", _("Name")),
    ("asset_type", _("Type")),
)


class _WalletAssetListState(TypedDict):
    """Filtered, sorted wallet-asset queryset plus the state that produced it."""

    queryset: QuerySet[VenueWalletAsset]
    current_sort: str
    filters_active: bool
    search: str
    asset_type: str


@login_required
def venue_overview(request: HttpRequest) -> HttpResponse:
    """List shared venues as a small responsive card grid."""
    venues = (
        Venue.objects.annotate(
            instrument_count=Count("instruments", distinct=True),
            wallet_asset_count=Count("wallet_assets", distinct=True),
        )
        .order_by("name")
    )
    return render(
        request,
        "tradefog/catalog/venue_overview.html",
        {
            "venues": venues,
            "can_manage": request.user.is_staff,
        },
    )


@login_required
def venue_create(request: HttpRequest) -> HttpResponse:
    """Render the create form fragment or accept a new catalog venue.

    A GET request supplies the modal form. A valid POST creates the venue and
    returns the refreshed card grid out of band; an invalid POST returns the
    form with field errors and a 422 status so the modal stays open.
    """
    if not request.user.is_staff:
        raise PermissionDenied
    form = VenueForm(request.POST or None)
    if request.method == "POST":
        if form.is_valid():
            try:
                form.save()
            except IntegrityError:
                form.add_error(
                    "name", _("A venue with this name already exists.")
                )
                return render(
                    request,
                    "tradefog/catalog/partials/venue_create_form.html",
                    {"form": form},
                    status=422,
                )
            context = _card_context(request)
            response = render(
                request,
                "tradefog/catalog/partials/venue_cards.html",
                context,
            )
            response["HX-Trigger"] = json.dumps(
                {
                    "tradefog:toast": {
                        "message": str(_("Venue added.")),
                        "kind": "success",
                    },
                    "tradefog:close-modal": {"id": "venue-create-modal"},
                }
            )
            return response
        return render(
            request,
            "tradefog/catalog/partials/venue_create_form.html",
            {"form": form},
            status=422,
        )
    return render(
        request,
        "tradefog/catalog/partials/venue_create_form.html",
        {"form": form},
    )


@login_required
def venue_edit(request: HttpRequest, pk: int) -> HttpResponse:
    """Render the settings form fragment or update a catalog venue.

    The venue's name and website are edited inline on the venue detail page's
    Settings tab. A valid POST saves the venue and returns the refreshed
    settings form plus an out-of-band ``#venue-heading`` fragment so the page
    title follows a renamed venue; an invalid POST returns the form with field
    errors and a 422 status.
    """
    if not request.user.is_staff:
        raise PermissionDenied
    venue = get_object_or_404(Venue, pk=pk)
    form = VenueForm(request.POST or None, instance=venue)
    if request.method == "POST":
        if form.is_valid():
            try:
                form.save()
            except IntegrityError:
                form.add_error(
                    "name", _("A venue with this name already exists.")
                )
                return render(
                    request,
                    "tradefog/catalog/partials/venue_settings_form.html",
                    {"form": form, "venue": venue},
                    status=422,
                )
            settings_html = render_to_string(
                "tradefog/catalog/partials/venue_settings_form.html",
                {"form": form, "venue": venue},
            )
            heading_html = render_to_string(
                "tradefog/catalog/partials/venue_heading.html",
                {"venue": venue, "swap_oob": True},
            )
            response = HttpResponse(settings_html + heading_html)
            response["HX-Trigger"] = json.dumps(
                {
                    "tradefog:toast": {
                        "message": str(_("Venue updated.")),
                        "kind": "success",
                    }
                }
            )
            return response
        return render(
            request,
            "tradefog/catalog/partials/venue_settings_form.html",
            {"form": form, "venue": venue},
            status=422,
        )
    return render(
        request,
        "tradefog/catalog/partials/venue_settings_form.html",
        {"form": form, "venue": venue},
    )


@login_required
def venue_delete(request: HttpRequest, pk: int) -> HttpResponse:
    """Render a delete confirmation or remove a shared venue.

    A GET request supplies the confirmation form. A POST removes the venue and
    returns the refreshed card grid out of band. A venue that a profile,
    instrument, or wallet asset references keeps its row and returns a danger
    alert with a 409 status so the modal stays open.
    """
    if not request.user.is_staff:
        raise PermissionDenied
    venue = get_object_or_404(Venue, pk=pk)
    if request.method == "POST":
        try:
            venue.delete()  # pyright: ignore[reportUnusedCallResult]
        except ProtectedError:
            response = HttpResponse(status=409)
            response["HX-Trigger"] = json.dumps(
                {
                    "tradefog:toast": {
                        "message": str(_(
                            "This venue is in use and cannot be removed."
                        )),
                        "kind": "danger",
                    },
                    "tradefog:close-modal": {"id": "venue-delete-modal"},
                }
            )
            return response
        context = _card_context(request)
        response = render(
            request,
            "tradefog/catalog/partials/venue_cards.html",
            context,
        )
        response["HX-Trigger"] = json.dumps(
            {
                "tradefog:toast": {
                    "message": str(_("Venue removed.")),
                    "kind": "success",
                },
                "tradefog:close-modal": {"id": "venue-delete-modal"},
            }
        )
        return response
    return render(
        request,
        "tradefog/catalog/partials/venue_delete_confirm.html",
        {"venue": venue},
    )


@login_required
def venue_detail(request: HttpRequest, pk: int) -> HttpResponse:
    """Render one venue with its wallet assets and instrument sections.

    An HTMX request from a section filter or sort link carries a ``section``
    parameter so only that section's results wrapper is returned.
    """
    venue = get_object_or_404(Venue, pk=pk)
    can_manage = request.user.is_staff
    section = request.GET.get("section", "")
    if request.headers.get("HX-Request") == "true":
        if section == "wallet":
            return render(
                request,
                "tradefog/catalog/partials/wallet_asset_results.html",
                {"section": _wallet_asset_context(
                    request,
                    venue,
                    _wallet_asset_list_state(request, venue),
                    can_manage=can_manage,
                )},
            )
        if section == "instruments":
            from tradefog.journal.views.catalog.instruments import (
                instrument_context,
                instrument_list_state,
            )

            return render(
                request,
                "tradefog/catalog/partials/instrument_results.html",
                {"section": instrument_context(
                    request,
                    venue,
                    instrument_list_state(request, venue),
                    can_manage=can_manage,
                )},
            )
    wallet_state = _wallet_asset_list_state(request, venue)
    from tradefog.journal.views.catalog.instruments import (
        instrument_context,
        instrument_list_state,
    )

    instrument_state = instrument_list_state(request, venue)
    context = {
        "venue": venue,
        "can_manage": can_manage,
        "form": VenueForm(instance=venue),
        "search": wallet_state["search"],
        "asset_type": wallet_state["asset_type"],
        "asset_type_choices": AssetType.choices,
        "product_choices": ProductKind.choices,
        "wallet_asset_context": _wallet_asset_context(
            request, venue, wallet_state, can_manage=can_manage
        ),
        "i_search": instrument_state["search"],
        "i_product": instrument_state["product"],
        "instrument_context": instrument_context(
            request, venue, instrument_state, can_manage=can_manage
        ),
    }
    return render(request, "tradefog/catalog/venue_detail.html", context)


@login_required
def wallet_asset_add(request: HttpRequest, pk: int) -> HttpResponse:
    """Render the add form fragment or link a wallet asset on the venue.

    A GET request supplies the modal form. A valid POST creates the link and
    returns the refreshed wallet-asset results wrapper out of band; an invalid
    POST returns the form with field errors and a 422 status.
    """
    if not request.user.is_staff:
        raise PermissionDenied
    venue = get_object_or_404(Venue, pk=pk)
    form = VenueWalletAssetForm(request.POST or None, venue=venue)
    if request.method == "POST":
        if form.is_valid():
            try:
                form.save()  # pyright: ignore[reportUnusedCallResult]
            except IntegrityError:
                form.add_error(
                    "asset",
                    _("This asset is already available on the venue."),
                )
                return render(
                    request,
                    "tradefog/catalog/partials/wallet_asset_add_form.html",
                    {"form": form, "venue": venue},
                    status=422,
                )
            context = _wallet_asset_context(
                request,
                venue,
                _wallet_asset_list_state(request, venue),
                can_manage=True,
                swap_oob=True,
            )
            response = render(
                request,
                "tradefog/catalog/partials/wallet_asset_results.html",
                {"section": context},
            )
            response["HX-Trigger"] = json.dumps(
                {
                    "tradefog:toast": {
                        "message": str(_("Wallet asset added.")),
                        "kind": "success",
                    },
                    "tradefog:close-modal": {"id": "wallet-asset-add-modal"},
                }
            )
            return response
        return render(
            request,
            "tradefog/catalog/partials/wallet_asset_add_form.html",
            {"form": form, "venue": venue},
            status=422,
        )
    return render(
        request,
        "tradefog/catalog/partials/wallet_asset_add_form.html",
        {"form": form, "venue": venue},
    )


@login_required
def wallet_asset_remove(
    request: HttpRequest, pk: int, asset_pk: int
) -> HttpResponse:
    """Render a removal confirmation or unlink a wallet asset from the venue.

    A GET request supplies the confirmation form. A POST removes the link and
    returns the refreshed results wrapper out of band. A wallet asset that a
    profile wallet references keeps its row and returns a danger alert with a
    409 status so the modal stays open.
    """
    if not request.user.is_staff:
        raise PermissionDenied
    venue = get_object_or_404(Venue, pk=pk)
    wallet_asset = get_object_or_404(
        VenueWalletAsset, venue=venue, pk=asset_pk
    )
    if request.method == "POST":
        try:
            wallet_asset.delete()  # pyright: ignore[reportUnusedCallResult]
        except ProtectedError:
            response = HttpResponse(status=409)
            response["HX-Trigger"] = json.dumps(
                {
                    "tradefog:toast": {
                        "message": str(_(
                            "This wallet asset is in use and cannot be removed."
                        )),
                        "kind": "danger",
                    },
                    "tradefog:close-modal": {"id": "wallet-asset-remove-modal"},
                }
            )
            return response
        context = _wallet_asset_context(
            request,
            venue,
            _wallet_asset_list_state(request, venue),
            can_manage=True,
            swap_oob=True,
        )
        response = render(
            request,
            "tradefog/catalog/partials/wallet_asset_results.html",
            {"section": context},
        )
        response["HX-Trigger"] = json.dumps(
            {
                "tradefog:toast": {
                    "message": str(_("Wallet asset removed.")),
                    "kind": "success",
                },
                "tradefog:close-modal": {"id": "wallet-asset-remove-modal"},
            }
        )
        return response
    return render(
        request,
        "tradefog/catalog/partials/wallet_asset_remove_confirm.html",
        {"venue": venue, "wallet_asset": wallet_asset},
    )


def _card_context(request: HttpRequest) -> dict[str, Any]:
    """Build the card-grid context for the current request state."""
    venues = (
        Venue.objects.annotate(
            instrument_count=Count("instruments", distinct=True),
            wallet_asset_count=Count("wallet_assets", distinct=True),
        )
        .order_by("name")
    )
    return {
        "venues": venues,
        "can_manage": request.user.is_staff,
        "swap_oob": True,
    }


def _wallet_asset_list_state(
    request: HttpRequest, venue: Venue
) -> _WalletAssetListState:
    """Apply active filters and sorting to the venue wallet-asset queryset."""
    queryset = VenueWalletAsset.objects.filter(venue=venue).select_related(
        "asset"
    )
    search = request.GET.get("wa_q", "").strip()
    asset_type = request.GET.get("wa_asset_type", "").strip()
    if search:
        queryset = queryset.filter(
            Q(asset__symbol__icontains=search)
            | Q(asset__name__icontains=search)
        )
    if asset_type in AssetType.values:
        queryset = queryset.filter(asset__asset_type=asset_type)
    requested_sort = request.GET.get("wa_sort", "symbol")
    current_sort = (
        requested_sort if requested_sort in WALLET_ASSET_SORT_FIELDS else "symbol"
    )
    return {
        "queryset": queryset.order_by(*WALLET_ASSET_SORT_FIELDS[current_sort]),
        "current_sort": current_sort,
        "filters_active": bool(search or asset_type),
        "search": search,
        "asset_type": asset_type,
    }


def _wallet_asset_context(
    request: HttpRequest,
    venue: Venue,
    state: _WalletAssetListState,
    *,
    can_manage: bool,
    swap_oob: bool = False,
) -> dict[str, Any]:
    """Build the wallet-asset results context for the current request state."""
    context = build_results_context(
        request,
        queryset=state["queryset"],
        page_size=WALLET_ASSET_PAGE_SIZE,
        current_sort=state["current_sort"],
        columns=WALLET_ASSET_SORT_COLUMNS,
        filters_active=state["filters_active"],
        can_manage=can_manage,
        results_key="wallet_assets",
        swap_oob=swap_oob,
        sort_parameter="wa_sort",
        page_parameter="wa_page",
    )
    context["venue"] = venue
    return context
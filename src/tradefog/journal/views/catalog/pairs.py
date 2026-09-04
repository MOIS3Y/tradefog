"""Views for the shared trading pairs collection page.

Pairs are read by every authenticated user; staff members create and remove
them, guarded by ``is_staff``. The page reuses the shared catalog list
helpers so sorting, the asset filter, and pagination stay consistent with the
assets collection.
"""

from __future__ import annotations

import json
from typing import Any, TypedDict

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import IntegrityError
from django.db.models import Q, QuerySet
from django.db.models.deletion import ProtectedError
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, render
from django.utils.translation import gettext_lazy as _

from tradefog.journal.forms import TradingPairForm
from tradefog.journal.models import TradingPair
from tradefog.journal.models.enums import AssetType
from tradefog.journal.views.catalog.common import build_results_context

PAIR_PAGE_SIZE = 10

SORT_FIELDS = {
    "symbol": ("canonical_symbol", "id"),
    "-symbol": ("-canonical_symbol", "-id"),
    "base": ("base__symbol", "canonical_symbol", "id"),
    "-base": ("-base__symbol", "-canonical_symbol", "-id"),
    "quote": ("quote__symbol", "canonical_symbol", "id"),
    "-quote": ("-quote__symbol", "-canonical_symbol", "-id"),
}

SORT_COLUMNS = (
    ("base", _("Base asset")),
    ("quote", _("Quote asset")),
    ("symbol", _("Symbol")),
)


class _PairListState(TypedDict):
    """Filtered, sorted queryset plus the list state that produced it."""

    queryset: QuerySet[TradingPair]
    current_sort: str
    filters_active: bool
    search: str
    pair_type: str


@login_required
def pair_overview(request: HttpRequest) -> HttpResponse:
    """List shared trading pairs with server-side filters and sorting."""
    state = _pair_list_state(request)
    context = _results_context(request, state)
    context["search"] = state["search"]
    context["pair_type"] = state["pair_type"]
    context["pair_type_choices"] = _pair_type_choices()
    template = "tradefog/catalog/pair_overview.html"
    if request.headers.get("HX-Request") == "true":
        template = "tradefog/catalog/partials/pair_results.html"
    return render(request, template, context)


@login_required
def pair_create(request: HttpRequest) -> HttpResponse:
    """Render the create form fragment or accept a new catalog pair.

    A GET request supplies the modal form. A valid POST creates the pair and
    returns the refreshed results wrapper out of band; an invalid POST returns
    the form with field errors and a 422 status so the modal stays open.
    """
    if not request.user.is_staff:
        raise PermissionDenied
    form = TradingPairForm(request.POST or None)
    if request.method == "POST":
        if form.is_valid():
            try:
                form.save()  # pyright: ignore[reportUnusedCallResult]
            except IntegrityError:
                form.add_error(
                    "base", _("This trading pair already exists.")
                )
                return render(
                    request,
                    "tradefog/catalog/partials/pair_create_form.html",
                    {"form": form},
                    status=422,
                )
            context = _results_context(
                request, _pair_list_state(request), swap_oob=True
            )
            response = render(
                request,
                "tradefog/catalog/partials/pair_results.html",
                context,
            )
            response["HX-Trigger"] = json.dumps(
                {
                    "tradefog:toast": {
                        "message": str(_("Trading pair added.")),
                        "kind": "success",
                    },
                    "tradefog:close-modal": {"id": "pair-create-modal"},
                }
            )
            return response
        return render(
            request,
            "tradefog/catalog/partials/pair_create_form.html",
            {"form": form},
            status=422,
        )
    return render(
        request,
        "tradefog/catalog/partials/pair_create_form.html",
        {"form": form},
    )


@login_required
def pair_delete(request: HttpRequest, pk: int) -> HttpResponse:
    """Render a delete confirmation or remove a shared catalog pair.

    A GET request supplies the confirmation form. A POST removes the pair and
    returns the refreshed results wrapper out of band. A protected pair that a
    venue instrument references keeps its row and returns a danger alert with
    a 409 status so the modal stays open.
    """
    if not request.user.is_staff:
        raise PermissionDenied
    pair = get_object_or_404(TradingPair, pk=pk)
    if request.method == "POST":
        try:
            pair.delete()  # pyright: ignore[reportUnusedCallResult]
        except ProtectedError:
            message = str(_(
                "This trading pair is in use and cannot be removed."
            ))
            response = HttpResponse(status=409)
            response["HX-Trigger"] = json.dumps(
                {
                    "tradefog:toast": {
                        "message": message,
                        "kind": "danger",
                    },
                    "tradefog:close-modal": {"id": "pair-delete-modal"},
                }
            )
            return response
        context = _results_context(
            request, _pair_list_state(request), swap_oob=True
        )
        response = render(
            request,
            "tradefog/catalog/partials/pair_results.html",
            context,
        )
        response["HX-Trigger"] = json.dumps(
            {
                "tradefog:toast": {
                    "message": str(_("Trading pair removed.")),
                    "kind": "success",
                },
                "tradefog:close-modal": {"id": "pair-delete-modal"},
            }
        )
        return response
    return render(
        request,
        "tradefog/catalog/partials/pair_delete_confirm.html",
        {"pair": pair},
    )


def _pair_type_choices() -> list[tuple[str, str]]:
    """Build the dynamic ``BASE_TYPE/QUOTE_TYPE`` filter options.

    Options are derived from the distinct base/quote asset-type combinations
    present in the catalog so the filter only ever offers real pair types.
    """
    combos = (
        TradingPair.objects.values_list(
            "base__asset_type", "quote__asset_type"
        )
        .distinct()
        .order_by("base__asset_type", "quote__asset_type")
    )
    choices: list[tuple[str, str]] = []
    for base_type, quote_type in combos:
        label = f"{AssetType(base_type).label} / {AssetType(quote_type).label}"
        choices.append((f"{base_type}/{quote_type}", label))
    return choices


def _pair_list_state(request: HttpRequest) -> _PairListState:
    """Apply active filters and sorting to the shared pair queryset."""
    queryset = TradingPair.objects.select_related("base", "quote")
    search = request.GET.get("q", "").strip()
    pair_type = request.GET.get("pair_type", "").strip()
    if search:
        queryset = queryset.filter(
            Q(canonical_symbol__icontains=search)
            | Q(base__symbol__icontains=search)
            | Q(base__name__icontains=search)
            | Q(quote__symbol__icontains=search)
            | Q(quote__name__icontains=search)
        )
    if pair_type and "/" in pair_type:
        base_type, quote_type = pair_type.split("/", 1)
        queryset = queryset.filter(
            base__asset_type=base_type,
            quote__asset_type=quote_type,
        )
    requested_sort = request.GET.get("sort", "symbol")
    current_sort = (
        requested_sort if requested_sort in SORT_FIELDS else "symbol"
    )
    return {
        "queryset": queryset.order_by(*SORT_FIELDS[current_sort]),
        "current_sort": current_sort,
        "filters_active": bool(search or pair_type),
        "search": search,
        "pair_type": pair_type,
    }


def _results_context(
    request: HttpRequest,
    state: _PairListState,
    *,
    swap_oob: bool = False,
) -> dict[str, Any]:
    """Build the results wrapper context for the current request state."""
    return build_results_context(
        request,
        queryset=state["queryset"],
        page_size=PAIR_PAGE_SIZE,
        current_sort=state["current_sort"],
        columns=SORT_COLUMNS,
        filters_active=state["filters_active"],
        can_manage=request.user.is_staff,
        results_key="pairs",
        swap_oob=swap_oob,
    )
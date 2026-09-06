"""Views for the shared asset collection page.

The catalog is read by every authenticated user. Staff members additionally
create and remove catalog records from the assets collection page; those
actions are guarded by ``is_staff`` so regular user queries never write to
the shared catalog.

HTMX list behavior renders only the ``#asset-results`` wrapper so sorting,
filtering, and pagination leave the page header and filter bar untouched.
Modal create and delete flows return the same wrapper as an out-of-band
fragment and rely on the modal script in ``tradefog.js`` to close on success.
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

from tradefog.journal.forms import AssetForm
from tradefog.journal.models import Asset
from tradefog.journal.models.enums import AssetType
from tradefog.journal.views.catalog.common import build_results_context

ASSET_PAGE_SIZE = 10

SORT_FIELDS = {
    "symbol": ("symbol", "id"),
    "-symbol": ("-symbol", "-id"),
    "name": ("name", "symbol", "id"),
    "-name": ("-name", "-symbol", "-id"),
    "asset_type": ("asset_type", "symbol", "id"),
    "-asset_type": ("-asset_type", "-symbol", "-id"),
}

SORT_COLUMNS = (
    ("symbol", _("Symbol")),
    ("name", _("Name")),
    ("asset_type", _("Type")),
)


class _AssetListState(TypedDict):
    """Filtered, sorted queryset plus the list state that produced it."""

    queryset: QuerySet[Asset]
    current_sort: str
    filters_active: bool
    search: str
    asset_type: str


@login_required
def asset_overview(request: HttpRequest) -> HttpResponse:
    """List shared catalog assets with server-side filters and sorting."""
    state = _asset_list_state(request)
    context = _results_context(request, state)
    context["asset_type_choices"] = AssetType.choices
    context["search"] = state["search"]
    context["asset_type"] = state["asset_type"]
    template = "tradefog/catalog/asset_overview.html"
    if request.headers.get("HX-Request") == "true":
        template = "tradefog/catalog/partials/asset_results.html"
    return render(request, template, context)


@login_required
def asset_create(request: HttpRequest) -> HttpResponse:
    """Render the create form fragment or accept a new catalog asset.

    A GET request supplies the modal form. A valid POST creates the asset and
    returns the refreshed results wrapper as an out-of-band fragment, while an
    invalid POST returns the form with field errors and a 422 status so the
    modal stays open.
    """
    if not request.user.is_staff:
        raise PermissionDenied
    form = AssetForm(request.POST or None)
    if request.method == "POST":
        if form.is_valid():
            try:
                form.save()
            except IntegrityError:
                form.add_error(
                    "symbol",
                    _("An asset with this symbol already exists."),
                )
                return render(
                    request,
                    "tradefog/catalog/partials/asset_create_form.html",
                    {"form": form},
                    status=422,
                )
            context = _results_context(
                request, _asset_list_state(request), swap_oob=True
            )
            response = render(
                request,
                "tradefog/catalog/partials/asset_results.html",
                context,
            )
            response["HX-Trigger"] = json.dumps(
                {
                    "tradefog:toast": {
                        "message": str(_("Asset added.")),
                        "kind": "success",
                    },
                    "tradefog:close-modal": {"id": "asset-create-modal"},
                }
            )
            return response
        return render(
            request,
            "tradefog/catalog/partials/asset_create_form.html",
            {"form": form},
            status=422,
        )
    return render(
        request,
        "tradefog/catalog/partials/asset_create_form.html",
        {"form": form},
    )


@login_required
def asset_delete(request: HttpRequest, pk: int) -> HttpResponse:
    """Render a delete confirmation or remove a shared catalog asset.

    A GET request supplies the confirmation form. A POST removes the asset
    and returns the refreshed results wrapper out of band. A protected asset
    that other catalog records reference keeps its row and returns a danger
    alert with a 409 status so the modal stays open.
    """
    if not request.user.is_staff:
        raise PermissionDenied
    asset = get_object_or_404(Asset, pk=pk)
    if request.method == "POST":
        try:
            asset.delete()  # pyright: ignore[reportUnusedCallResult]
        except ProtectedError:
            response = HttpResponse(status=409)
            response["HX-Trigger"] = json.dumps(
                {
                    "tradefog:toast": {
                        "message": str(
                            _("This asset is in use and cannot be removed.")
                        ),
                        "kind": "danger",
                    },
                    "tradefog:close-modal": {"id": "asset-delete-modal"},
                }
            )
            return response
        context = _results_context(
            request, _asset_list_state(request), swap_oob=True
        )
        response = render(
            request,
            "tradefog/catalog/partials/asset_results.html",
            context,
        )
        response["HX-Trigger"] = json.dumps(
            {
                "tradefog:toast": {
                    "message": str(_("Asset removed.")),
                    "kind": "success",
                },
                "tradefog:close-modal": {"id": "asset-delete-modal"},
            }
        )
        return response
    return render(
        request,
        "tradefog/catalog/partials/asset_delete_confirm.html",
        {"asset": asset},
    )


def _asset_list_state(request: HttpRequest) -> _AssetListState:
    """Apply active filters and sorting to the shared asset queryset."""
    queryset = Asset.objects.all()
    search = request.GET.get("q", "").strip()
    asset_type = request.GET.get("asset_type", "").strip()
    if search:
        queryset = queryset.filter(
            Q(symbol__icontains=search) | Q(name__icontains=search)
        )
    if asset_type in AssetType.values:
        queryset = queryset.filter(asset_type=asset_type)
    requested_sort = request.GET.get("sort", "symbol")
    current_sort = (
        requested_sort if requested_sort in SORT_FIELDS else "symbol"
    )
    return {
        "queryset": queryset.order_by(*SORT_FIELDS[current_sort]),
        "current_sort": current_sort,
        "filters_active": bool(search or asset_type),
        "search": search,
        "asset_type": asset_type,
    }


def _results_context(
    request: HttpRequest,
    state: _AssetListState,
    *,
    swap_oob: bool = False,
) -> dict[str, Any]:
    """Build the results wrapper context for the current request state."""
    return build_results_context(
        request,
        queryset=state["queryset"],
        page_size=ASSET_PAGE_SIZE,
        current_sort=state["current_sort"],
        columns=SORT_COLUMNS,
        filters_active=state["filters_active"],
        can_manage=request.user.is_staff,
        results_key="assets",
        swap_oob=swap_oob,
    )

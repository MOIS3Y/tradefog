"""Views for the shared, staff-managed reference catalog.

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
from typing import TypedDict

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.paginator import Page, Paginator
from django.db import IntegrityError
from django.db.models import Q, QuerySet
from django.db.models.deletion import ProtectedError
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, render
from django.utils.translation import gettext_lazy as _

from tradefog.journal.forms import AssetForm
from tradefog.journal.models import Asset
from tradefog.journal.models.enums import AssetType

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
    page_obj = Paginator(
        state["queryset"],
        ASSET_PAGE_SIZE,
    ).get_page(request.GET.get("page"))
    context = {
        "page_obj": page_obj,
        "assets": page_obj.object_list,
        "pagination": _pagination_urls(request, page_obj),
        "sort_headers": _sort_headers(request, state["current_sort"]),
        "filters_active": state["filters_active"],
        "search": state["search"],
        "asset_type": state["asset_type"],
        "asset_type_choices": AssetType.choices,
        "can_manage": request.user.is_staff,
        "swap_oob": False,
    }
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
            context = _results_context(request, swap_oob=True)
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
                        "message": str(_(
                            "This asset is in use and cannot be removed."
                        )),
                        "kind": "danger",
                    },
                    "tradefog:close-modal": {"id": "asset-delete-modal"},
                }
            )
            return response
        context = _results_context(request, swap_oob=True)
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
    *,
    swap_oob: bool = False,
) -> dict[str, object]:
    """Build the results wrapper context for the current request state."""
    state = _asset_list_state(request)
    page_obj = Paginator(
        state["queryset"],
        ASSET_PAGE_SIZE,
    ).get_page(request.GET.get("page"))
    return {
        "page_obj": page_obj,
        "assets": page_obj.object_list,
        "pagination": _pagination_urls(request, page_obj),
        "sort_headers": _sort_headers(request, state["current_sort"]),
        "filters_active": state["filters_active"],
        "can_manage": request.user.is_staff,
        "swap_oob": swap_oob,
    }


def _sort_headers(
    request: HttpRequest,
    current_sort: str,
    *,
    sort_parameter: str = "sort",
    page_parameter: str = "page",
) -> tuple[dict[str, str | bool], ...]:
    """Build safe sort links while preserving the active filter query."""
    headers: list[dict[str, str | bool]] = []
    for key, label in SORT_COLUMNS:
        active = current_sort.lstrip("-") == key
        descending = current_sort == f"-{key}"
        next_sort = key if descending or not active else f"-{key}"
        query = request.GET.copy()
        query[sort_parameter] = next_sort
        _removed_page = query.pop(page_parameter, None)
        headers.append(
            {
                "key": key,
                "label": label,
                "url": f"?{query.urlencode()}",
                "active": active,
                "descending": descending,
            }
        )
    return tuple(headers)


def _pagination_urls(
    request: HttpRequest,
    page_obj: Page,
    page_parameter: str = "page",
) -> dict[str, str | None]:
    """Preserve all list state while changing one page parameter."""
    previous_url = None
    next_url = None
    if page_obj.has_previous():
        previous_query = request.GET.copy()
        previous_query[page_parameter] = str(
            page_obj.previous_page_number()
        )
        previous_url = f"?{previous_query.urlencode()}"
    if page_obj.has_next():
        next_query = request.GET.copy()
        next_query[page_parameter] = str(page_obj.next_page_number())
        next_url = f"?{next_query.urlencode()}"
    return {"previous_url": previous_url, "next_url": next_url}

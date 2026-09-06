"""Views for executable venue instruments on the shared catalog.

Instruments are managed from the venue detail page where they form one of two
table sections. Staff create, edit, delist (toggle ``active``), and remove
instruments through modal flows and an inline toggle; regular users only read
the section. Every mutating action is guarded by ``is_staff``.
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

from tradefog.journal.forms import VenueInstrumentForm
from tradefog.journal.models import Venue, VenueInstrument
from tradefog.journal.models.enums import ProductKind
from tradefog.journal.views.catalog.common import build_results_context

INSTRUMENT_PAGE_SIZE = 10

INSTRUMENT_SORT_FIELDS = {
    "pair": ("pair__canonical_symbol", "id"),
    "-pair": ("-pair__canonical_symbol", "-id"),
    "product": ("product", "pair__canonical_symbol", "id"),
    "-product": ("-product", "-pair__canonical_symbol", "-id"),
    "exec_symbol": ("exec_symbol", "pair__canonical_symbol", "id"),
    "-exec_symbol": ("-exec_symbol", "-pair__canonical_symbol", "-id"),
    "settlement": ("settlement_asset__symbol", "pair__canonical_symbol", "id"),
    "-settlement": (
        "-settlement_asset__symbol",
        "-pair__canonical_symbol",
        "-id",
    ),
}

INSTRUMENT_SORT_COLUMNS = (
    ("pair", _("Pair")),
    ("product", _("Product")),
    ("exec_symbol", _("Execution symbol")),
    ("settlement", _("Settlement")),
)


class _InstrumentListState(TypedDict):
    """Filtered, sorted instrument queryset plus the state that produced it."""

    queryset: QuerySet[VenueInstrument]
    current_sort: str
    filters_active: bool
    search: str
    product: str


@login_required
def instrument_add(request: HttpRequest, pk: int) -> HttpResponse:
    """Render the add form fragment or accept a new venue instrument.

    A GET request supplies the modal form. A valid POST creates the instrument
    and returns the refreshed instrument results wrapper out of band; an
    invalid POST returns the form with field errors and a 422 status.
    """
    if not request.user.is_staff:
        raise PermissionDenied
    venue = get_object_or_404(Venue, pk=pk)
    form = VenueInstrumentForm(request.POST or None, venue=venue)
    if request.method == "POST":
        if form.is_valid():
            try:
                form.save()  # pyright: ignore[reportUnusedCallResult]
            except IntegrityError:
                form.add_error(
                    "exec_symbol",
                    _("This execution symbol already exists on the venue."),
                )
                return render(
                    request,
                    "tradefog/catalog/partials/instrument_add_form.html",
                    {"form": form, "venue": venue},
                    status=422,
                )
            context = instrument_context(
                request,
                venue,
                instrument_list_state(request, venue),
                can_manage=True,
                swap_oob=True,
            )
            response = render(
                request,
                "tradefog/catalog/partials/instrument_results.html",
                {"section": context},
            )
            response["HX-Trigger"] = json.dumps(
                {
                    "tradefog:toast": {
                        "message": str(_("Instrument added.")),
                        "kind": "success",
                    },
                    "tradefog:close-modal": {"id": "instrument-add-modal"},
                }
            )
            return response
        return render(
            request,
            "tradefog/catalog/partials/instrument_add_form.html",
            {"form": form, "venue": venue},
            status=422,
        )
    return render(
        request,
        "tradefog/catalog/partials/instrument_add_form.html",
        {"form": form, "venue": venue},
    )


@login_required
def instrument_edit(
    request: HttpRequest, pk: int, instrument_pk: int
) -> HttpResponse:
    """Render the edit form fragment or update a venue instrument.

    A GET request supplies the modal form. A valid POST updates the instrument
    and returns the refreshed results wrapper out of band; an invalid POST
    returns the form with field errors and a 422 status.
    """
    if not request.user.is_staff:
        raise PermissionDenied
    venue = get_object_or_404(Venue, pk=pk)
    instrument = get_object_or_404(
        VenueInstrument, venue=venue, pk=instrument_pk
    )
    form = VenueInstrumentForm(
        request.POST or None, instance=instrument, venue=venue
    )
    if request.method == "POST":
        if form.is_valid():
            try:
                form.save()  # pyright: ignore[reportUnusedCallResult]
            except IntegrityError:
                form.add_error(
                    "exec_symbol",
                    _("This execution symbol already exists on the venue."),
                )
                return render(
                    request,
                    "tradefog/catalog/partials/instrument_edit_form.html",
                    {"form": form, "venue": venue, "instrument": instrument},
                    status=422,
                )
            context = instrument_context(
                request,
                venue,
                instrument_list_state(request, venue),
                can_manage=True,
                swap_oob=True,
            )
            response = render(
                request,
                "tradefog/catalog/partials/instrument_results.html",
                {"section": context},
            )
            response["HX-Trigger"] = json.dumps(
                {
                    "tradefog:toast": {
                        "message": str(_("Instrument updated.")),
                        "kind": "success",
                    },
                    "tradefog:close-modal": {"id": "instrument-edit-modal"},
                }
            )
            return response
        return render(
            request,
            "tradefog/catalog/partials/instrument_edit_form.html",
            {"form": form, "venue": venue, "instrument": instrument},
            status=422,
        )
    return render(
        request,
        "tradefog/catalog/partials/instrument_edit_form.html",
        {"form": form, "venue": venue, "instrument": instrument},
    )


@login_required
def instrument_detail(
    request: HttpRequest, pk: int, instrument_pk: int
) -> HttpResponse:
    """Render the read-only details of one venue instrument.

    Any authenticated user, staff or not, can inspect the instrument's
    parameters. The fragment is loaded into a modal by a per-row button.
    """
    venue = get_object_or_404(Venue, pk=pk)
    instrument = get_object_or_404(
        VenueInstrument.objects.select_related(
            "pair__base", "pair__quote", "settlement_asset"
        ),
        venue=venue,
        pk=instrument_pk,
    )
    return render(
        request,
        "tradefog/catalog/partials/instrument_detail.html",
        {"venue": venue, "instrument": instrument},
    )


@login_required
def instrument_delete(
    request: HttpRequest, pk: int, instrument_pk: int
) -> HttpResponse:
    """Render a delete confirmation or remove a venue instrument.

    A GET request supplies the confirmation form. A POST removes the
    instrument and returns the refreshed results wrapper out of band. An
    instrument that a trade references keeps its row and returns a danger alert
    with a 409 status so the modal stays open.
    """
    if not request.user.is_staff:
        raise PermissionDenied
    venue = get_object_or_404(Venue, pk=pk)
    instrument = get_object_or_404(
        VenueInstrument, venue=venue, pk=instrument_pk
    )
    if request.method == "POST":
        try:
            instrument.delete()  # pyright: ignore[reportUnusedCallResult]
        except ProtectedError:
            response = HttpResponse(status=409)
            response["HX-Trigger"] = json.dumps(
                {
                    "tradefog:toast": {
                        "message": str(
                            _(
                                "This instrument is in use and cannot be removed."
                            )
                        ),
                        "kind": "danger",
                    },
                    "tradefog:close-modal": {"id": "instrument-delete-modal"},
                }
            )
            return response
        context = instrument_context(
            request,
            venue,
            instrument_list_state(request, venue),
            can_manage=True,
            swap_oob=True,
        )
        response = render(
            request,
            "tradefog/catalog/partials/instrument_results.html",
            {"section": context},
        )
        response["HX-Trigger"] = json.dumps(
            {
                "tradefog:toast": {
                    "message": str(_("Instrument removed.")),
                    "kind": "success",
                },
                "tradefog:close-modal": {"id": "instrument-delete-modal"},
            }
        )
        return response
    return render(
        request,
        "tradefog/catalog/partials/instrument_delete_confirm.html",
        {"venue": venue, "instrument": instrument},
    )


def instrument_list_state(
    request: HttpRequest, venue: Venue
) -> _InstrumentListState:
    """Apply active filters and sorting to the venue instrument queryset."""
    queryset = VenueInstrument.objects.filter(venue=venue).select_related(
        "pair__base", "pair__quote", "settlement_asset"
    )
    search = request.GET.get("i_q", "").strip()
    product = request.GET.get("i_product", "").strip()
    if search:
        queryset = queryset.filter(
            Q(pair__canonical_symbol__icontains=search)
            | Q(exec_symbol__icontains=search)
            | Q(pair__base__symbol__icontains=search)
            | Q(pair__quote__symbol__icontains=search)
        )
    if product in ProductKind.values:
        queryset = queryset.filter(product=product)
    requested_sort = request.GET.get("i_sort", "pair")
    current_sort = (
        requested_sort if requested_sort in INSTRUMENT_SORT_FIELDS else "pair"
    )
    return {
        "queryset": queryset.order_by(*INSTRUMENT_SORT_FIELDS[current_sort]),
        "current_sort": current_sort,
        "filters_active": bool(search or product),
        "search": search,
        "product": product,
    }


def instrument_context(
    request: HttpRequest,
    venue: Venue,
    state: _InstrumentListState,
    *,
    can_manage: bool,
    swap_oob: bool = False,
) -> dict[str, Any]:
    """Build the instrument results context for the current request state."""
    context = build_results_context(
        request,
        queryset=state["queryset"],
        page_size=INSTRUMENT_PAGE_SIZE,
        current_sort=state["current_sort"],
        columns=INSTRUMENT_SORT_COLUMNS,
        filters_active=state["filters_active"],
        can_manage=can_manage,
        results_key="instruments",
        swap_oob=swap_oob,
        sort_parameter="i_sort",
        page_parameter="i_page",
    )
    context["venue"] = venue
    return context

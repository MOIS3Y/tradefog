"""Owner-scoped wallet views for one profile.

The wallet tab renders a small grid of wallet-asset cards plus a paginated,
sortable table of the wallet's operations. Mutations run through confirmation
modals and refresh the whole wallet content out of band. Management is
disabled for archived profiles: their wallet stays readable but cannot change.
"""

from __future__ import annotations

import json
from decimal import Decimal
from typing import Any, TypedDict

from django.contrib.auth.decorators import login_required
from django.db import IntegrityError
from django.db.models import QuerySet, Sum
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, render
from django.utils.translation import gettext_lazy as _

from tradefog.journal.calculations import (
    wallet_asset_status,
    wallet_balance,
)
from tradefog.journal.forms import (
    WalletAssetAddForm,
    WalletAssetEditForm,
    WalletOperationForm,
)
from tradefog.journal.models import (
    TradingProfile,
    Wallet,
    WalletAsset,
    WalletOperation,
)
from tradefog.journal.models.enums import WalletOperationKind
from tradefog.journal.views.catalog.common import build_results_context

OPERATION_PAGE_SIZE = 10

OPERATION_SORT_FIELDS = {
    "created_at": ("-created_at", "-id"),
    "-created_at": ("-created_at", "-id"),
    "asset": (
        "wallet_asset__venue_wallet_asset__asset__symbol",
        "-created_at",
        "id",
    ),
    "-asset": (
        "-wallet_asset__venue_wallet_asset__asset__symbol",
        "-created_at",
        "id",
    ),
    "kind": ("kind", "-created_at", "id"),
    "-kind": ("-kind", "-created_at", "id"),
    "amount": ("amount", "-created_at", "id"),
    "-amount": ("-amount", "-created_at", "id"),
}

OPERATION_SORT_COLUMNS = (
    ("created_at", _("Date")),
    ("asset", _("Asset")),
    ("kind", _("Kind")),
    ("amount", _("Amount")),
)


class _AssetSummary(TypedDict):
    """A wallet asset with its derived balance and status."""

    asset: WalletAsset
    balance: Decimal
    status: str


@login_required
def wallet_add(
    request: HttpRequest, pk: int
) -> HttpResponse:
    """Render an add form fragment or link an asset to the wallet."""
    profile = _get_profile(request, pk)
    if profile.archived:
        return _archived_response("wallet-add-modal")
    wallet = _wallet_of(profile)
    form = WalletAssetAddForm(
        request.POST or None, wallet=wallet
    )
    if request.method == "POST":
        if form.is_valid():
            try:
                form.save()  # pyright: ignore[reportUnusedCallResult]
            except IntegrityError:
                form.add_error(
                    "venue_wallet_asset",
                    _("This asset is already in the wallet."),
                )
                return render(
                    request,
                    "tradefog/profiles/partials/wallet_add_form.html",
                    {"form": form, "profile": profile},
                    status=422,
                )
            return _wallet_response(
                request,
                profile,
                message=_("Asset added to wallet."),
                close_modal="wallet-add-modal",
            )
        return render(
            request,
            "tradefog/profiles/partials/wallet_add_form.html",
            {"form": form, "profile": profile},
            status=422,
        )
    return render(
        request,
        "tradefog/profiles/partials/wallet_add_form.html",
        {"form": form, "profile": profile},
    )


@login_required
def wallet_deposit(
    request: HttpRequest, pk: int, asset_pk: int
) -> HttpResponse:
    """Render a deposit form fragment or record a deposit operation."""
    return _wallet_operation(
        request, pk, asset_pk, WalletOperationKind.DEPOSIT
    )


@login_required
def wallet_withdraw(
    request: HttpRequest, pk: int, asset_pk: int
) -> HttpResponse:
    """Render a withdrawal form fragment or record a withdrawal operation."""
    return _wallet_operation(
        request, pk, asset_pk, WalletOperationKind.WITHDRAWAL
    )


@login_required
def wallet_edit(
    request: HttpRequest, pk: int, asset_pk: int
) -> HttpResponse:
    """Render an edit form fragment or update the asset deposit floor."""
    profile = _get_profile(request, pk)
    if profile.archived:
        return _archived_response("wallet-edit-modal")
    wallet_asset = _wallet_asset(request, pk, asset_pk)
    form = WalletAssetEditForm(request.POST or None, instance=wallet_asset)
    if request.method == "POST":
        if form.is_valid():
            form.save()
            return _wallet_response(
                request,
                profile,
                message=_("Asset updated."),
                close_modal="wallet-edit-modal",
            )
        return render(
            request,
            "tradefog/profiles/partials/wallet_edit_form.html",
            {"form": form, "profile": profile, "wallet_asset": wallet_asset},
            status=422,
        )
    return render(
        request,
        "tradefog/profiles/partials/wallet_edit_form.html",
        {"form": form, "profile": profile, "wallet_asset": wallet_asset},
    )


def _wallet_operation(
    request: HttpRequest,
    pk: int,
    asset_pk: int,
    kind: str,
) -> HttpResponse:
    """Render an operation form fragment or record an operation."""
    profile = _get_profile(request, pk)
    if profile.archived:
        close_modal = (
            "wallet-withdraw-modal"
            if kind == WalletOperationKind.WITHDRAWAL.value
            else "wallet-deposit-modal"
        )
        return _archived_response(close_modal)
    wallet_asset = _wallet_asset(request, pk, asset_pk)
    template = (
        "tradefog/profiles/partials/wallet_withdraw_form.html"
        if kind == WalletOperationKind.WITHDRAWAL.value
        else "tradefog/profiles/partials/wallet_deposit_form.html"
    )
    form = WalletOperationForm(
        request.POST or None,
        wallet_asset=wallet_asset,
        kind=kind,
    )
    if request.method == "POST":
        if form.is_valid():
            form.save()  # pyright: ignore[reportUnusedCallResult]
            message = (
                _("Withdrawal recorded.")
                if kind == WalletOperationKind.WITHDRAWAL.value
                else _("Deposit recorded.")
            )
            close_modal = (
                "wallet-withdraw-modal"
                if kind == WalletOperationKind.WITHDRAWAL.value
                else "wallet-deposit-modal"
            )
            return _wallet_response(
                request,
                profile,
                message=message,
                close_modal=close_modal,
            )
        return render(
            request,
            template,
            {
                "form": form,
                "profile": profile,
                "wallet_asset": wallet_asset,
            },
            status=422,
        )
    return render(
        request,
        template,
        {
            "form": form,
            "profile": profile,
            "wallet_asset": wallet_asset,
        },
    )


def wallet_context(
    request: HttpRequest,
    profile: TradingProfile,
    *,
    swap_oob: bool = False,
) -> dict[str, Any]:
    """Build the wallet tab context for one profile."""
    wallet = _wallet_of(profile)
    asset_rows = [
        _summarize_asset(asset)
        for asset in wallet.assets.select_related(
            "venue_wallet_asset__asset"
        ).order_by("venue_wallet_asset__asset__symbol")
    ]
    operations_state = _operation_list_state(request, wallet)
    section = build_results_context(
        request,
        queryset=operations_state["queryset"],
        page_size=OPERATION_PAGE_SIZE,
        current_sort=operations_state["current_sort"],
        columns=OPERATION_SORT_COLUMNS,
        filters_active=False,
        can_manage=not profile.archived,
        results_key="operations",
        swap_oob=False,
        sort_parameter="op_sort",
        page_parameter="op_page",
    )
    return {
        "profile": profile,
        "wallet": wallet,
        "asset_rows": asset_rows,
        "can_manage": not profile.archived,
        "operations": section["operations"],
        "page_obj": section["page_obj"],
        "pagination": section["pagination"],
        "sort_headers": section["sort_headers"],
        "swap_oob": swap_oob,
    }


def _summarize_asset(asset: WalletAsset) -> _AssetSummary:
    """Derive the balance and status of one wallet asset."""
    total_deposits = asset.operations.filter(
        kind=WalletOperationKind.DEPOSIT
    ).aggregate(total=Sum("amount"))["total"] or Decimal(0)
    total_withdrawals = asset.operations.filter(
        kind=WalletOperationKind.WITHDRAWAL
    ).aggregate(total=Sum("amount"))["total"] or Decimal(0)
    balance = wallet_balance(total_deposits, total_withdrawals)
    return {
        "asset": asset,
        "balance": balance,
        "status": wallet_asset_status(
            balance, asset.risk_stop_capital
        ),
    }


def _operation_list_state(
    request: HttpRequest, wallet: Wallet
) -> dict[str, Any]:
    """Apply the requested sort to the wallet's operation queryset."""
    queryset: QuerySet[WalletOperation] = WalletOperation.objects.filter(
        wallet_asset__wallet=wallet
    ).select_related("wallet_asset__venue_wallet_asset__asset")
    requested_sort = request.GET.get("op_sort", "-created_at")
    current_sort = (
        requested_sort
        if requested_sort in OPERATION_SORT_FIELDS
        else "-created_at"
    )
    queryset = queryset.order_by(*OPERATION_SORT_FIELDS[current_sort])
    return {
        "queryset": queryset,
        "current_sort": current_sort,
    }


def _wallet_of(profile: TradingProfile) -> Wallet:
    """Return the profile wallet, creating it if it is missing."""
    wallet, _created = Wallet.objects.get_or_create(profile=profile)
    return wallet


def _get_profile(
    request: HttpRequest, pk: int
) -> TradingProfile:
    """Return the current user's profile or raise a 404."""
    return get_object_or_404(
        TradingProfile, pk=pk, owner=request.user
    )


def _wallet_asset(
    request: HttpRequest, pk: int, asset_pk: int
) -> WalletAsset:
    """Return an owner-scoped wallet asset or raise a 404."""
    return get_object_or_404(
        WalletAsset,
        pk=asset_pk,
        wallet__profile__owner=request.user,
        wallet__profile__pk=pk,
    )


def _wallet_response(
    request: HttpRequest,
    profile: TradingProfile,
    *,
    message: str,
    close_modal: str,
) -> HttpResponse:
    """Render the refreshed wallet content out of band with a toast."""
    response = render(
        request,
        "tradefog/profiles/partials/wallet_content.html",
        {"section": wallet_context(request, profile, swap_oob=True)},
    )
    response["HX-Trigger"] = json.dumps(
        {
            "tradefog:toast": {
                "message": str(message),
                "kind": "success",
            },
            "tradefog:close-modal": {"id": close_modal},
        }
    )
    return response


def _archived_response(close_modal: str) -> HttpResponse:
    """Refuse a wallet mutation on an archived profile."""
    response = HttpResponse(status=409)
    response["HX-Trigger"] = json.dumps(
        {
            "tradefog:toast": {
                "message": str(_(
                    "Restore the profile to manage its wallet."
                )),
                "kind": "danger",
            },
            "tradefog:close-modal": {"id": close_modal},
        }
    )
    return response
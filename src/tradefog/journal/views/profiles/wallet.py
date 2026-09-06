"""Owner-scoped wallet views for one profile.

The wallet tab renders a small grid of wallet-asset cards plus a paginated,
sortable table of the wallet's operations. Mutations run through confirmation
modals and refresh the whole wallet content out of band. Management is
disabled for archived profiles: their wallet stays readable but cannot change.
"""

from __future__ import annotations

import json
from decimal import Decimal
from http import HTTPStatus
from typing import Any, TypedDict

from django.contrib.auth.decorators import login_required
from django.db import IntegrityError
from django.db.models import QuerySet, Sum
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, render
from django.template.loader import render_to_string
from django.utils.translation import gettext_lazy as _

from tradefog.journal.calculations import (
    available_balance,
    wallet_asset_status,
    wallet_balance,
)
from tradefog.journal.forms import (
    WalletAssetAddForm,
    WalletAssetEditForm,
    WalletOperationForm,
    WalletOperationNoteForm,
)
from tradefog.journal.models import (
    StrategyCapital,
    TradingProfile,
    VenueWalletAsset,
    Wallet,
    WalletAsset,
    WalletOperation,
)
from tradefog.journal.models.enums import WalletOperationKind
from tradefog.journal.services import reserved_notional
from tradefog.journal.views.catalog.common import build_results_context
from tradefog.journal.views.profiles.common import profile_overview_html

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
    """A wallet asset with its derived balance, reservation, and status."""

    asset: WalletAsset
    balance: Decimal
    reserved: Decimal
    available: Decimal
    status: str
    is_delisted: bool
    is_archived: bool


@login_required
def wallet_add(request: HttpRequest, pk: int) -> HttpResponse:
    """Render an add form fragment or link an asset to the wallet."""
    profile = _get_profile(request, pk)
    if profile.is_archived:
        return _archived_response("wallet-add-modal")
    wallet = _wallet_of(profile)
    venue_has_wallet_assets = VenueWalletAsset.objects.filter(
        venue=profile.venue, is_active=True
    ).exists()
    can_manage = request.user.is_staff
    form = WalletAssetAddForm(request.POST or None, wallet=wallet)
    context: dict[str, Any] = {
        "form": form,
        "profile": profile,
        "venue_has_wallet_assets": venue_has_wallet_assets,
        "can_manage": can_manage,
    }
    if request.method == "POST":
        if not venue_has_wallet_assets:
            return HttpResponse(status=HTTPStatus.CONFLICT)
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
                    context,
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
            context,
            status=422,
        )
    return render(
        request,
        "tradefog/profiles/partials/wallet_add_form.html",
        context,
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
def wallet_edit(request: HttpRequest, pk: int, asset_pk: int) -> HttpResponse:
    """Render an edit form fragment or update the asset deposit floor."""
    profile = _get_profile(request, pk)
    if profile.is_archived:
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


@login_required
def wallet_operation_edit(
    request: HttpRequest, pk: int, operation_pk: int
) -> HttpResponse:
    """Render an edit form fragment or update an operation's note."""
    profile = _get_profile(request, pk)
    if profile.is_archived:
        return _archived_response("wallet-operation-edit-modal")
    operation = _operation(request, pk, operation_pk)
    form = WalletOperationNoteForm(request.POST or None, instance=operation)
    if request.method == "POST":
        if form.is_valid():
            form.save()
            return _wallet_response(
                request,
                profile,
                message=_("Operation note updated."),
                close_modal="wallet-operation-edit-modal",
            )
        return render(
            request,
            "tradefog/profiles/partials/wallet_operation_edit_form.html",
            {
                "form": form,
                "profile": profile,
                "operation": operation,
            },
            status=422,
        )
    return render(
        request,
        "tradefog/profiles/partials/wallet_operation_edit_form.html",
        {
            "form": form,
            "profile": profile,
            "operation": operation,
        },
    )


@login_required
def wallet_remove(
    request: HttpRequest, pk: int, asset_pk: int
) -> HttpResponse:
    """Remove an unreferenced wallet asset or archive a zero-balance asset."""
    profile = _get_profile(request, pk)
    if profile.is_archived:
        return _archived_response("wallet-remove-modal")
    wallet_asset = _wallet_asset(request, pk, asset_pk)
    has_operations = WalletOperation.objects.filter(
        wallet_asset=wallet_asset
    ).exists()
    has_capitals = StrategyCapital.objects.filter(
        wallet_asset=wallet_asset
    ).exists()
    can_hard_delete = not has_operations and not has_capitals

    if request.method == "GET":
        return render(
            request,
            "tradefog/profiles/partials/wallet_remove_confirm.html",
            {
                "profile": profile,
                "wallet_asset": wallet_asset,
                "can_hard_delete": can_hard_delete,
            },
        )

    if can_hard_delete:
        wallet_asset.delete()  # pyright: ignore[reportUnusedCallResult]
        return _wallet_response(
            request,
            profile,
            message=_("Asset removed from wallet."),
            close_modal="wallet-remove-modal",
        )

    summary = _summarize_asset(wallet_asset, profile)
    if summary["balance"] != Decimal(0):
        response = HttpResponse(status=409)
        response["HX-Trigger"] = json.dumps(
            {
                "tradefog:toast": {
                    "message": str(
                        _(
                            "Withdraw or convert all funds so the balance is zero "
                            + "before archiving this asset."
                        )
                    ),
                    "kind": "danger",
                },
                "tradefog:close-modal": {"id": "wallet-remove-modal"},
            }
        )
        return response

    if StrategyCapital.objects.filter(
        wallet_asset=wallet_asset, is_archived=False
    ).exists():
        response = HttpResponse(status=409)
        response["HX-Trigger"] = json.dumps(
            {
                "tradefog:toast": {
                    "message": str(
                        _(
                            "Archive all strategy allocations for this asset "
                            + "before archiving it."
                        )
                    ),
                    "kind": "danger",
                },
                "tradefog:close-modal": {"id": "wallet-remove-modal"},
            }
        )
        return response

    wallet_asset.is_archived = True
    wallet_asset.save(update_fields=["is_archived"])
    return _wallet_response(
        request,
        profile,
        message=_("Asset archived."),
        close_modal="wallet-remove-modal",
    )


@login_required
def wallet_restore(
    request: HttpRequest, pk: int, asset_pk: int
) -> HttpResponse:
    """Restore an archived wallet asset back to the active wallet grid."""
    profile = _get_profile(request, pk)
    if profile.is_archived:
        return _archived_response("wallet-restore-modal")
    wallet_asset = _wallet_asset(request, pk, asset_pk)
    if not wallet_asset.is_archived:
        return _inactive_action_response("wallet-restore-modal")
    if not wallet_asset.venue_wallet_asset.is_active:
        response = HttpResponse(status=409)
        response["HX-Trigger"] = json.dumps(
            {
                "tradefog:toast": {
                    "message": str(
                        _(
                            "This asset is delisted on the venue and cannot be restored."
                        )
                    ),
                    "kind": "danger",
                },
            }
        )
        return response
    wallet_asset.is_archived = False
    wallet_asset.save(update_fields=["is_archived"])
    return _wallet_response(
        request,
        profile,
        message=_("Asset restored."),
        close_modal="wallet-restore-modal",
    )


def _wallet_operation(
    request: HttpRequest,
    pk: int,
    asset_pk: int,
    kind: str,
) -> HttpResponse:
    """Render an operation form fragment or record an operation."""
    profile = _get_profile(request, pk)
    if profile.is_archived:
        close_modal = (
            "wallet-withdraw-modal"
            if kind == WalletOperationKind.WITHDRAWAL.value
            else "wallet-deposit-modal"
        )
        return _archived_response(close_modal)
    wallet_asset = _wallet_asset(request, pk, asset_pk)
    if (
        kind == WalletOperationKind.DEPOSIT.value
        and not wallet_asset.venue_wallet_asset.is_active
    ):
        response = HttpResponse(status=409)
        response["HX-Trigger"] = json.dumps(
            {
                "tradefog:toast": {
                    "message": str(
                        _(
                            "Deposits are not allowed for delisted venue assets."
                        )
                    ),
                    "kind": "danger",
                },
                "tradefog:close-modal": {"id": "wallet-deposit-modal"},
            }
        )
        return response
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
    all_rows = [
        _summarize_asset(asset, profile)
        for asset in wallet.assets.select_related(
            "venue_wallet_asset__asset"
        ).order_by("venue_wallet_asset__asset__symbol")
    ]
    active_asset_rows = [r for r in all_rows if not r["is_archived"]]
    archived_asset_rows = [r for r in all_rows if r["is_archived"]]
    operations_state = _operation_list_state(request, wallet)
    section = build_results_context(
        request,
        queryset=operations_state["queryset"],
        page_size=OPERATION_PAGE_SIZE,
        current_sort=operations_state["current_sort"],
        columns=OPERATION_SORT_COLUMNS,
        filters_active=False,
        can_manage=not profile.is_archived,
        results_key="operations",
        swap_oob=False,
        sort_parameter="op_sort",
        page_parameter="op_page",
    )
    return {
        "profile": profile,
        "wallet": wallet,
        "asset_rows": active_asset_rows,
        "archived_asset_rows": archived_asset_rows,
        "has_archived_assets": bool(archived_asset_rows),
        "can_manage": not profile.is_archived,
        "operations": section["operations"],
        "page_obj": section["page_obj"],
        "pagination": section["pagination"],
        "sort_headers": section["sort_headers"],
        "swap_oob": swap_oob,
    }


def _summarize_asset(
    asset: WalletAsset, profile: TradingProfile
) -> _AssetSummary:
    """Derive the balance, reservation, and status of one wallet asset."""
    total_deposits = asset.operations.filter(
        kind=WalletOperationKind.DEPOSIT
    ).aggregate(total=Sum("amount"))["total"] or Decimal(0)
    total_withdrawals = asset.operations.filter(
        kind=WalletOperationKind.WITHDRAWAL
    ).aggregate(total=Sum("amount"))["total"] or Decimal(0)
    balance = wallet_balance(total_deposits, total_withdrawals)
    reserved = reserved_notional(profile, asset.venue_wallet_asset.asset_id)
    available = available_balance(balance, reserved)
    return {
        "asset": asset,
        "balance": balance,
        "reserved": reserved,
        "available": available,
        "status": wallet_asset_status(
            balance, available, asset.risk_stop_capital
        ),
        "is_delisted": not asset.venue_wallet_asset.is_active,
        "is_archived": asset.is_archived,
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


def _get_profile(request: HttpRequest, pk: int) -> TradingProfile:
    """Return the current user's profile or raise a 404."""
    return get_object_or_404(TradingProfile, pk=pk, owner=request.user)


def _wallet_asset(request: HttpRequest, pk: int, asset_pk: int) -> WalletAsset:
    """Return an owner-scoped wallet asset or raise a 404."""
    return get_object_or_404(
        WalletAsset,
        pk=asset_pk,
        wallet__profile__owner=request.user,
        wallet__profile__pk=pk,
    )


def _operation(
    request: HttpRequest, pk: int, operation_pk: int
) -> WalletOperation:
    """Return an owner-scoped wallet operation or raise a 404."""
    return get_object_or_404(
        WalletOperation,
        pk=operation_pk,
        wallet_asset__wallet__profile__owner=request.user,
        wallet_asset__wallet__profile__pk=pk,
    )


def _wallet_response(
    request: HttpRequest,
    profile: TradingProfile,
    *,
    message: str,
    close_modal: str,
) -> HttpResponse:
    """Render refreshed wallet and overview contents out of band with a toast."""
    wallet_html = render_to_string(
        "tradefog/profiles/partials/wallet_content.html",
        {"section": wallet_context(request, profile, swap_oob=True)},
        request=request,
    )
    overview_html = profile_overview_html(request, profile)
    response = HttpResponse(wallet_html + overview_html)
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
                "message": str(_("Restore the profile to manage its wallet.")),
                "kind": "danger",
            },
            "tradefog:close-modal": {"id": close_modal},
        }
    )
    return response


def _inactive_action_response(close_modal: str) -> HttpResponse:
    """Refuse an action that is already the entity state."""
    response = HttpResponse(status=409)
    response["HX-Trigger"] = json.dumps(
        {
            "tradefog:toast": {
                "message": str(_("The asset already has this status.")),
                "kind": "danger",
            },
            "tradefog:close-modal": {"id": close_modal},
        }
    )
    return response

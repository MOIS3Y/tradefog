"""Views for trade creation, workspace, and cascading selectors."""

from decimal import Decimal
from typing import Any

from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.translation import gettext_lazy as _
from django.views.decorators.http import require_http_methods

from tradefog.journal.forms.trades import ChecklistForm, TradeDecisionForm
from tradefog.journal.models import (
    StrategyCapital,
    Trade,
    TradingProfile,
    TradingStrategy,
    VenueInstrument,
)
from tradefog.journal.models.enums import ProductKind
from tradefog.journal.services import (
    reserved_notional,
    wallet_asset_balance,
)


def _get_context_bar_data(
    profile: TradingProfile | None,
    strategy: TradingStrategy | None,
    instrument: VenueInstrument | None,
) -> dict[str, Any]:
    """Assemble context data for the top persistent context bar."""
    if not profile or not strategy:
        return {
            "profile": profile,
            "strategy": strategy,
            "instrument": instrument,
            "fixed_1r": None,
            "wallet_available": None,
            "settlement_symbol": None,
        }

    settlement_id = None
    if instrument:
        settlement_id = (
            instrument.settlement_asset_id or instrument.pair.quote_id
        )

    capital_alloc = None
    if settlement_id:
        capital_alloc = (
            StrategyCapital.objects.filter(
                strategy=strategy,
                wallet_asset__venue_wallet_asset__asset_id=settlement_id,
                is_archived=False,
            )
            .select_related("wallet_asset__venue_wallet_asset__asset")
            .first()
        )
    else:
        capital_alloc = (
            StrategyCapital.objects.filter(
                strategy=strategy, is_archived=False
            )
            .select_related("wallet_asset__venue_wallet_asset__asset")
            .first()
        )

    fixed_1r = None
    wallet_avail = None
    settlement_symbol = None

    if capital_alloc:
        settlement_symbol = (
            capital_alloc.wallet_asset.venue_wallet_asset.asset.symbol
        )
        fixed_1r = capital_alloc.capital * (
            strategy.risk_percent / Decimal(100)
        )
        w_asset = capital_alloc.wallet_asset
        bal = wallet_asset_balance(w_asset)
        eff_asset_id = w_asset.venue_wallet_asset.asset_id
        res = reserved_notional(profile, eff_asset_id)
        wallet_avail = bal - res

    return {
        "profile": profile,
        "strategy": strategy,
        "instrument": instrument,
        "fixed_1r": fixed_1r,
        "wallet_available": wallet_avail,
        "settlement_symbol": settlement_symbol,
    }


@login_required
@require_http_methods(["GET", "POST"])
def trade_create(request: HttpRequest) -> HttpResponse:
    """Create a new trade draft and render the trade workspace."""
    profile_id = request.GET.get("profile") or request.POST.get("profile")
    strategy_id = request.GET.get("strategy") or request.POST.get("strategy")

    profile: TradingProfile | None = None
    if profile_id:
        profile = TradingProfile.objects.filter(
            pk=profile_id, owner=request.user, is_archived=False
        ).first()

    if not profile:
        profile = TradingProfile.objects.filter(
            owner=request.user, is_archived=False
        ).first()

    strategy: TradingStrategy | None = None
    if profile and strategy_id:
        strategy = TradingStrategy.objects.filter(
            pk=strategy_id, profile=profile, is_archived=False
        ).first()

    if profile and not strategy:
        strategy = TradingStrategy.objects.filter(
            profile=profile, is_archived=False
        ).first()

    if request.method == "POST":
        form = TradeDecisionForm(
            request.POST,
            user=request.user,
            profile=profile,
            strategy=strategy,
        )
        checklist_form = ChecklistForm(request.POST)

        if form.is_valid():
            trade = form.save(commit=False)
            trade.save()
            messages.success(
                request,
                _("Trade draft created successfully."),
            )
            return redirect("journal:trade_workspace", pk=trade.pk)
    else:
        form = TradeDecisionForm(
            user=request.user,
            profile=profile,
            strategy=strategy,
        )
        checklist_form = ChecklistForm()

    instrument: VenueInstrument | None = None
    instrument_field = form.fields.get("venue_instrument")
    if isinstance(instrument_field, forms.ModelChoiceField):
        first_obj = instrument_field.queryset.first()
        if isinstance(first_obj, VenueInstrument):
            instrument = first_obj

    context_bar = _get_context_bar_data(profile, strategy, instrument)

    context = {
        "form": form,
        "checklist_form": checklist_form,
        "context_bar": context_bar,
        "trade": None,
        "is_new": True,
    }
    return render(request, "tradefog/trades/workspace.html", context)


@login_required
@require_http_methods(["GET", "POST"])
def trade_workspace(request: HttpRequest, pk: int) -> HttpResponse:
    """Render full workspace for an existing trade."""
    trade = get_object_or_404(
        Trade.objects.select_related(
            "profile__venue",
            "profile__wallet",
            "strategy",
            "venue_instrument__pair__base",
            "venue_instrument__pair__quote",
        ),
        pk=pk,
        profile__owner=request.user,
    )

    if request.method == "POST":
        form = TradeDecisionForm(
            request.POST,
            instance=trade,
            user=request.user,
            profile=trade.profile,
            strategy=trade.strategy,
        )
        if form.is_valid():
            form.save()
            messages.success(request, _("Trade draft updated."))
            return redirect("journal:trade_workspace", pk=trade.pk)
    else:
        form = TradeDecisionForm(
            instance=trade,
            user=request.user,
            profile=trade.profile,
            strategy=trade.strategy,
        )

    checklist_form = ChecklistForm()
    context_bar = _get_context_bar_data(
        trade.profile, trade.strategy, trade.venue_instrument
    )

    context = {
        "form": form,
        "checklist_form": checklist_form,
        "context_bar": context_bar,
        "trade": trade,
        "is_new": False,
    }
    return render(request, "tradefog/trades/workspace.html", context)


@login_required
@require_http_methods(["GET"])
def trade_options(request: HttpRequest) -> HttpResponse:
    """HTMX endpoint returning cascading options for strategies and instruments."""
    profile_id = request.GET.get("profile")
    strategy_id = request.GET.get("strategy")
    product_kind_param = request.GET.get("product_kind")

    profile: TradingProfile | None = None
    if profile_id:
        profile = TradingProfile.objects.filter(
            pk=profile_id, owner=request.user, is_archived=False
        ).first()

    strategies: list[TradingStrategy] = []
    instruments: list[VenueInstrument] = []
    product_kinds: list[tuple[str, str]] = []
    selected_product_kind: str | None = None

    if profile:
        strategies = list(
            TradingStrategy.objects.filter(
                profile=profile, is_archived=False
            ).order_by("name")
        )

        selected_strategy = None
        if strategy_id:
            selected_strategy = next(
                (s for s in strategies if str(s.pk) == str(strategy_id)), None
            )
        if not selected_strategy and strategies:
            selected_strategy = strategies[0]

        if selected_strategy:
            allocated_ids = StrategyCapital.objects.filter(
                strategy=selected_strategy, is_archived=False
            ).values_list(
                "wallet_asset__venue_wallet_asset__asset_id", flat=True
            )
            all_instruments = list(
                VenueInstrument.objects.filter(
                    venue=profile.venue, is_active=True
                )
                .filter(
                    Q(settlement_asset_id__in=allocated_ids)
                    | Q(
                        settlement_asset__isnull=True,
                        pair__quote_id__in=allocated_ids,
                    )
                )
                .select_related("pair__base", "pair__quote")
                .order_by("exec_symbol")
            )

            available_kinds = sorted(
                {inst.product for inst in all_instruments}
            )
            product_kinds = [
                (kind, str(ProductKind(kind).label))
                for kind in available_kinds
            ]

            if product_kind_param and product_kind_param in available_kinds:
                selected_product_kind = product_kind_param
            elif available_kinds:
                selected_product_kind = available_kinds[0]

            if selected_product_kind:
                instruments = [
                    inst
                    for inst in all_instruments
                    if inst.product == selected_product_kind
                ]
            else:
                instruments = all_instruments

    context = {
        "strategies": strategies,
        "instruments": instruments,
        "product_kinds": product_kinds,
        "selected_strategy_id": strategy_id,
        "selected_product_kind": selected_product_kind,
    }
    return render(request, "tradefog/trades/partials/options.html", context)

"""Views for trade workspace, trade creation, and reactive JSON endpoints."""

import datetime
import json
import logging
from decimal import Decimal
from typing import Any

logger = logging.getLogger(__name__)

from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ObjectDoesNotExist
from django.db.models import Q
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.translation import gettext_lazy as _
from django.views.decorators.http import require_http_methods

from tradefog.journal.forms.trades import ChecklistForm, TradeDecisionForm
from tradefog.journal.markdown import render_markdown
from tradefog.journal.models import (
    StrategyCapital,
    Trade,
    TradingProfile,
    TradingStrategy,
    VenueInstrument,
)
from tradefog.journal.models.enums import MarketDataProvider, ProductKind
from tradefog.journal.presentation import compact_decimal
from tradefog.journal.services import (
    reserved_notional,
    wallet_asset_balance,
)
from tradefog.market import MarketDataError, fetch_atr_context


def _get_context_bar_data(
    profile: TradingProfile | None,
    strategy: TradingStrategy | None,
    instrument: VenueInstrument | None,
) -> dict[str, Any]:
    """Assemble context data for the top persistent context bar."""
    if not profile or not strategy:
        return {
            "profile": profile,
            "venue": profile.venue if profile else None,
            "strategy": strategy,
            "instrument": instrument,
            "fixed_1r": None,
            "wallet_available": None,
            "settlement_symbol": None,
            "market_data_provider": (
                profile.venue.market_data_provider
                if profile and profile.venue
                else MarketDataProvider.NONE
            ),
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
        "venue": profile.venue,
        "strategy": strategy,
        "instrument": instrument,
        "fixed_1r": fixed_1r,
        "wallet_available": wallet_avail,
        "settlement_symbol": settlement_symbol,
        "market_data_provider": profile.venue.market_data_provider,
    }


def _get_instruments_for_strategy(
    profile: TradingProfile, strategy: TradingStrategy | None
) -> list[VenueInstrument]:
    """Return all active venue instruments compatible with strategy allocations."""
    if not strategy:
        return []
    allocated_ids = StrategyCapital.objects.filter(
        strategy=strategy, is_archived=False
    ).values_list("wallet_asset__venue_wallet_asset__asset_id", flat=True)
    return list(
        VenueInstrument.objects.filter(venue=profile.venue, is_active=True)
        .filter(
            Q(settlement_asset_id__in=allocated_ids)
            | Q(
                settlement_asset__isnull=True,
                pair__quote_id__in=allocated_ids,
            )
        )
        .select_related(
            "pair__base", "pair__quote", "settlement_asset", "venue"
        )
        .order_by("exec_symbol")
    )


def _serialize_instrument(inst: VenueInstrument) -> dict[str, Any]:
    """Serialize a venue instrument for frontend state."""
    settlement_sym = (
        inst.settlement_asset.symbol
        if inst.settlement_asset
        else inst.pair.quote.symbol
    )
    return {
        "id": inst.pk,
        "exec_symbol": inst.exec_symbol,
        "canonical_symbol": inst.pair.canonical_symbol,
        "product": inst.product,
        "product_label": str(ProductKind(inst.product).label),
        "price_step": compact_decimal(inst.price_step),
        "qty_step": compact_decimal(inst.qty_step),
        "min_qty": (
            compact_decimal(inst.min_qty) if inst.min_qty is not None else None
        ),
        "min_notional": (
            compact_decimal(inst.min_notional)
            if inst.min_notional is not None
            else None
        ),
        "settlement_symbol": settlement_sym,
    }


def _serialize_strategy(strat: TradingStrategy) -> dict[str, Any]:
    """Serialize a strategy for frontend state."""
    return {
        "id": strat.pk,
        "name": strat.name,
        "risk_percent": compact_decimal(strat.risk_percent),
        "reward_multiple": compact_decimal(strat.reward_multiple),
    }


def extract_draft_context(data: Any) -> dict[str, Any]:
    """Extract serializable non-model form values for the draft."""
    keys = (
        "planned_entry",
        "planned_stop",
        "product_kind",
        "market_sentiment",
        "information_background",
        "global_daily_direction",
        "local_daily_movement",
        "manual_atr_value",
        "manual_session_range",
        "auto_atr_value",
        "atr_contributing_date",
        "observed_session_range",
        "session_range_percent",
        "atr_source",
    )
    result: dict[str, Any] = {}
    for k in keys:
        val = data.get(k)
        if val is not None:
            s_val = str(val).strip()
            if s_val:
                result[k] = s_val

    raw_candles = data.get("candles_data")
    if raw_candles:
        if isinstance(raw_candles, list):
            result["candles_data"] = raw_candles
        elif isinstance(raw_candles, str):
            trimmed = raw_candles.strip()
            if trimmed:
                try:
                    parsed = json.loads(trimmed)
                    if isinstance(parsed, list):
                        result["candles_data"] = parsed
                except (json.JSONDecodeError, TypeError) as exc:
                    logger.debug("Failed to decode candles_data JSON: %s", exc)
    return result


def _build_workspace_config(
    *,
    profile: TradingProfile,
    strategy: TradingStrategy | None,
    instrument: VenueInstrument | None,
    trade: Trade | None = None,
    draft_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build complete JSON config payload for trade-workspace.js."""
    strategies = list(
        TradingStrategy.objects.filter(
            profile=profile, is_archived=False
        ).order_by("name")
    )
    instruments = _get_instruments_for_strategy(profile, strategy)
    ctx_bar = _get_context_bar_data(profile, strategy, instrument)

    saved_ctx = draft_context or (trade.draft_context if trade else {}) or {}

    planned_entry = saved_ctx.get("planned_entry", "")
    planned_stop = saved_ctx.get("planned_stop", "")
    snapshot_atr_val: str | None = None
    snapshot_atr_src: str | None = None
    snapshot_atr_date: str | None = None

    if trade:
        try:
            snapshot = trade.snapshot
            if snapshot is not None:
                planned_entry = str(snapshot.planned_entry)
                planned_stop = str(snapshot.planned_stop)
                if snapshot.atr_value is not None:
                    snapshot_atr_val = compact_decimal(snapshot.atr_value)
                if snapshot.atr_source:
                    snapshot_atr_src = snapshot.atr_source
                if snapshot.atr_contributing_date:
                    snapshot_atr_date = (
                        snapshot.atr_contributing_date.isoformat()
                    )
        except ObjectDoesNotExist:
            pass

    is_read_only = trade is not None and trade.status != "draft"

    effective_atr_val = (
        snapshot_atr_val
        or saved_ctx.get("auto_atr_value")
        or saved_ctx.get("manual_atr_value")
        or ""
    )
    effective_atr_date = (
        snapshot_atr_date
        or saved_ctx.get("atr_contributing_date")
        or ""
    )
    effective_session_range = (
        saved_ctx.get("observed_session_range")
        or saved_ctx.get("manual_session_range")
        or ""
    )
    effective_session_pct = saved_ctx.get("session_range_percent") or ""

    return {
        "is_new": trade is None,
        "trade_id": trade.pk if trade else None,
        "status": trade.status if trade else "draft",
        "is_read_only": is_read_only,
        "selected_profile_id": profile.pk,
        "selected_strategy_id": strategy.pk if strategy else None,
        "selected_instrument_id": instrument.pk if instrument else None,
        "product_kind": (
            instrument.product
            if instrument
            else saved_ctx.get("product_kind", "")
        ),
        "direction": (trade.direction if trade else "long").lower(),
        "trade_date": (
            trade.trade_date.isoformat()
            if trade
            else datetime.datetime.now(datetime.UTC).date().isoformat()
        ),
        "planned_entry": planned_entry,
        "planned_stop": planned_stop,
        "atr_source": snapshot_atr_src or saved_ctx.get("atr_source", "auto"),
        "atr_value": effective_atr_val,
        "atr_contributing_date": effective_atr_date,
        "observed_session_range": effective_session_range,
        "session_range_percent": effective_session_pct,
        "candles_data": saved_ctx.get("candles_data", []),
        "manual_atr_value": saved_ctx.get("manual_atr_value", ""),
        "manual_session_range": saved_ctx.get("manual_session_range", ""),
        "checklist": {
            "market_sentiment": saved_ctx.get("market_sentiment", "NEUTRAL"),
            "information_background": saved_ctx.get(
                "information_background", "NEUTRAL"
            ),
            "global_daily_direction": saved_ctx.get(
                "global_daily_direction", "NEUTRAL"
            ),
            "local_daily_movement": saved_ctx.get(
                "local_daily_movement", "NEUTRAL"
            ),
        },
        "strategies": [_serialize_strategy(s) for s in strategies],
        "instruments": [_serialize_instrument(inst) for inst in instruments],
        "context_bar": {
            "profile_name": profile.name,
            "venue_name": profile.venue.name,
            "market_data_provider": profile.venue.market_data_provider,
            "strategy_name": strategy.name if strategy else None,
            "reward_multiple": (
                compact_decimal(strategy.reward_multiple) if strategy else "3"
            ),
            "risk_percent": (
                compact_decimal(strategy.risk_percent) if strategy else "1"
            ),
            "fixed_1r": (
                f"{ctx_bar['fixed_1r']:.2f}"
                if ctx_bar["fixed_1r"] is not None
                else None
            ),
            "wallet_available": (
                f"{ctx_bar['wallet_available']:.2f}"
                if ctx_bar["wallet_available"] is not None
                else None
            ),
            "settlement_symbol": ctx_bar["settlement_symbol"],
        },
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

    if not profile:
        messages.warning(
            request,
            _("Create a trading profile before starting a new trade."),
        )
        return redirect("journal:profile_overview")

    strategy: TradingStrategy | None = None
    if profile and strategy_id:
        strategy = TradingStrategy.objects.filter(
            pk=strategy_id, profile=profile, is_archived=False
        ).first()

    if not strategy:
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
            trade.draft_context = extract_draft_context(request.POST)
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
    workspace_config = _build_workspace_config(
        profile=profile,
        strategy=strategy,
        instrument=instrument,
        draft_context=extract_draft_context(request.GET),
    )

    context = {
        "form": form,
        "checklist_form": checklist_form,
        "context_bar": context_bar,
        "workspace_config": workspace_config,
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
            "venue_instrument__settlement_asset",
            "snapshot",
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
            saved_trade = form.save(commit=False)
            if saved_trade.status == "draft":
                saved_trade.draft_context = extract_draft_context(
                    request.POST
                )
            saved_trade.save()
            messages.success(request, _("Trade draft updated."))
            return redirect("journal:trade_workspace", pk=trade.pk)
    else:
        form = TradeDecisionForm(
            instance=trade,
            user=request.user,
            profile=trade.profile,
            strategy=trade.strategy,
        )

    checklist_initial: dict[str, Any] | None = trade.draft_context or None
    checklist_form = ChecklistForm(initial=checklist_initial)
    context_bar = _get_context_bar_data(
        trade.profile, trade.strategy, trade.venue_instrument
    )
    workspace_config = _build_workspace_config(
        profile=trade.profile,
        strategy=trade.strategy,
        instrument=trade.venue_instrument,
        trade=trade,
    )

    rendered_description = render_markdown(trade.description_markdown)

    context = {
        "form": form,
        "checklist_form": checklist_form,
        "context_bar": context_bar,
        "workspace_config": workspace_config,
        "trade": trade,
        "rendered_description": rendered_description,
        "is_new": False,
    }
    return render(request, "tradefog/trades/workspace.html", context)


@login_required
@require_http_methods(["GET"])
def trade_workspace_options(request: HttpRequest) -> JsonResponse:
    """JSON endpoint returning cascading options for strategies and instruments."""
    profile_id = request.GET.get("profile")
    strategy_id = request.GET.get("strategy")

    profile: TradingProfile | None = None
    if profile_id:
        profile = TradingProfile.objects.filter(
            pk=profile_id, owner=request.user, is_archived=False
        ).first()

    if not profile:
        profile = TradingProfile.objects.filter(
            owner=request.user, is_archived=False
        ).first()

    if not profile:
        return JsonResponse({"error": "No trading profile available"}, status=404)

    strategies = list(
        TradingStrategy.objects.filter(
            profile=profile, is_archived=False
        ).order_by("name")
    )

    selected_strategy: TradingStrategy | None = None
    if strategy_id:
        selected_strategy = next(
            (s for s in strategies if str(s.pk) == str(strategy_id)), None
        )
    if not selected_strategy and strategies:
        selected_strategy = strategies[0]

    instruments = _get_instruments_for_strategy(profile, selected_strategy)
    selected_instrument = instruments[0] if instruments else None

    ctx_bar = _get_context_bar_data(
        profile, selected_strategy, selected_instrument
    )

    return JsonResponse(
        {
            "strategies": [_serialize_strategy(s) for s in strategies],
            "instruments": [_serialize_instrument(inst) for inst in instruments],
            "selected_strategy_id": (
                selected_strategy.pk if selected_strategy else None
            ),
            "selected_instrument_id": (
                selected_instrument.pk if selected_instrument else None
            ),
            "context_bar": {
                "profile_name": profile.name,
                "venue_name": profile.venue.name,
                "market_data_provider": profile.venue.market_data_provider,
                "strategy_name": (
                    selected_strategy.name if selected_strategy else None
                ),
                "reward_multiple": (
                    compact_decimal(selected_strategy.reward_multiple)
                    if selected_strategy
                    else "3"
                ),
                "risk_percent": (
                    compact_decimal(selected_strategy.risk_percent)
                    if selected_strategy
                    else "1"
                ),
                "fixed_1r": (
                    f"{ctx_bar['fixed_1r']:.2f}"
                    if ctx_bar["fixed_1r"] is not None
                    else None
                ),
                "wallet_available": (
                    f"{ctx_bar['wallet_available']:.2f}"
                    if ctx_bar["wallet_available"] is not None
                    else None
                ),
                "settlement_symbol": ctx_bar["settlement_symbol"],
            },
        }
    )



@login_required
@require_http_methods(["GET"])
def trade_market_data(request: HttpRequest) -> JsonResponse:
    """JSON endpoint returning on-demand candles and calculated ATR context."""
    instrument_id = request.GET.get("instrument")
    trade_date_raw = request.GET.get("trade_date", "").strip()

    if not instrument_id:
        return JsonResponse(
            {"status": "error", "message": "Missing instrument ID"}, status=400
        )

    instrument = get_object_or_404(
        VenueInstrument.objects.select_related("venue", "pair"),
        pk=instrument_id,
        is_active=True,
    )

    trade_date: datetime.date | None = None
    if trade_date_raw:
        try:
            trade_date = datetime.date.fromisoformat(trade_date_raw)
        except ValueError:
            trade_date = None

    if trade_date is None:
        trade_date = datetime.datetime.now(datetime.UTC).date()

    provider = str(instrument.venue.market_data_provider)

    if provider == MarketDataProvider.NONE.value:
        return JsonResponse(
            {
                "status": "manual",
                "provider": provider,
                "atr_value": None,
                "candles": [],
                "message": str(
                    _("Venue is configured for manual ATR input only.")
                ),
            }
        )

    try:
        atr_ctx = fetch_atr_context(
            provider=provider,
            symbol=instrument.exec_symbol,
            product_kind=instrument.product,
            trade_date=trade_date,
        )
        candles_data = [
            {
                "date": candle.date.isoformat(),
                "open": float(candle.open),
                "high": float(candle.high),
                "low": float(candle.low),
                "close": float(candle.close),
            }
            for candle in atr_ctx.candles
        ]
        return JsonResponse(
            {
                "status": "ok",
                "provider": provider,
                "atr_value": str(atr_ctx.atr_value),
                "contributing_date": atr_ctx.contributing_date.isoformat(),
                "is_stale": atr_ctx.is_stale,
                "observed_session_range": (
                    str(atr_ctx.observed_session_range)
                    if atr_ctx.observed_session_range is not None
                    else None
                ),
                "session_range_percent": (
                    str(atr_ctx.session_range_percent)
                    if atr_ctx.session_range_percent is not None
                    else None
                ),
                "candles": candles_data,
            }
        )
    except MarketDataError as err:
        return JsonResponse(
            {
                "status": "error",
                "provider": provider,
                "message": str(err),
            }
        )

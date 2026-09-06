"""HTMX endpoint for reactive calculation of position plan and risk."""

from decimal import Decimal, InvalidOperation
from typing import Any

from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_http_methods

from tradefog.journal.calculations import (
    PositionPlanError,
    calculate_position_plan,
)
from tradefog.journal.models import (
    StrategyCapital,
    TradingStrategy,
    VenueInstrument,
)
from tradefog.journal.services import (
    reserved_notional,
    wallet_asset_balance,
)


@login_required
@require_http_methods(["GET", "POST"])
def trade_plan_preview(request: HttpRequest) -> HttpResponse:
    """Calculate and render position plan fragment from form inputs."""
    data = request.POST if request.method == "POST" else request.GET

    strategy_id = data.get("strategy")
    instrument_id = data.get("venue_instrument")
    direction = data.get("direction", "LONG")
    entry_raw = data.get("planned_entry", "").strip()
    stop_raw = data.get("planned_stop", "").strip()

    context: dict[str, Any] = {
        "plan": None,
        "error": None,
        "direction": direction,
    }

    if not strategy_id or not instrument_id or not entry_raw or not stop_raw:
        return render(
            request,
            "tradefog/trades/partials/position_plan.html",
            context,
        )

    # Scoped lookups
    strategy = get_object_or_404(
        TradingStrategy,
        pk=strategy_id,
        profile__owner=request.user,
        is_archived=False,
    )
    instrument = get_object_or_404(
        VenueInstrument,
        pk=instrument_id,
        venue=strategy.profile.venue,
        is_active=True,
    )

    try:
        entry = Decimal(entry_raw)
        stop = Decimal(stop_raw)
    except (InvalidOperation, ValueError):
        context["error"] = "Invalid price input format."
        return render(
            request,
            "tradefog/trades/partials/position_plan.html",
            context,
        )

    settlement_id = instrument.settlement_asset_id or instrument.pair.quote_id
    capital_allocation = (
        StrategyCapital.objects.filter(
            strategy=strategy,
            wallet_asset__venue_wallet_asset__asset_id=settlement_id,
            is_archived=False,
        )
        .select_related("wallet_asset__venue_wallet_asset__asset")
        .first()
    )

    if not capital_allocation:
        context["error"] = (
            "Strategy has no capital allocation for this instrument."
        )
        return render(
            request,
            "tradefog/trades/partials/position_plan.html",
            context,
        )

    target_risk = capital_allocation.capital * (
        strategy.risk_percent / Decimal(100)
    )

    try:
        plan = calculate_position_plan(
            direction=direction,
            entry=entry,
            stop=stop,
            target_risk_amount=target_risk,
            reward_multiple=strategy.reward_multiple,
            price_step=instrument.price_step,
            quantity_step=instrument.qty_step,
            minimum_quantity=instrument.min_qty,
            minimum_notional=instrument.min_notional,
        )
        context["plan"] = plan
        context["settlement_symbol"] = (
            capital_allocation.wallet_asset.venue_wallet_asset.asset.symbol
        )
        context["base_symbol"] = instrument.pair.base.symbol

        # Check wallet capacity
        wallet_asset = capital_allocation.wallet_asset
        balance = wallet_asset_balance(wallet_asset)
        reserved = reserved_notional(strategy.profile, settlement_id)
        available = balance - reserved
        context["available_balance"] = available
        context["capacity_after_plan"] = available - plan.notional
        context["exceeds_wallet"] = plan.notional > available

    except PositionPlanError as error:
        context["error"] = error.message

    return render(
        request,
        "tradefog/trades/partials/position_plan.html",
        context,
    )

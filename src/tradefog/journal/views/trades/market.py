"""HTMX endpoint for on-demand market candles and ATR context."""

import datetime
import json
from decimal import Decimal, InvalidOperation
from typing import Any

from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_http_methods

from tradefog.journal.models import TradingStrategy, VenueInstrument
from tradefog.market import MarketDataError, fetch_bybit_atr_context


@login_required
@require_http_methods(["GET", "POST"])
def trade_market_preview(request: HttpRequest) -> HttpResponse:
    """Fetch on-demand market candles and calculate ATR context."""
    data = request.POST if request.method == "POST" else request.GET

    instrument_id = data.get("venue_instrument")
    strategy_id = data.get("strategy")
    trade_date_raw = data.get("trade_date", "").strip()
    entry_raw = data.get("planned_entry", "").strip()
    stop_raw = data.get("planned_stop", "").strip()

    atr_source = data.get("atr_source", "auto").strip().lower()
    manual_atr_raw = data.get("manual_atr_value", "").strip()
    manual_session_raw = data.get("manual_session_range", "").strip()

    context: dict[str, Any] = {
        "market_context": None,
        "candles_json": "[]",
        "error": None,
        "instrument": None,
        "reference_75_atr": None,
        "planned_move": None,
        "planned_move_percent": None,
        "exceeds_75_atr": False,
        "atr_source": atr_source,
        "manual_atr_value": manual_atr_raw,
        "manual_session_range": manual_session_raw,
    }

    if not instrument_id:
        return render(
            request,
            "tradefog/trades/partials/market_context.html",
            context,
        )

    instrument = get_object_or_404(
        VenueInstrument,
        pk=instrument_id,
        is_active=True,
    )
    context["instrument"] = instrument

    trade_date: datetime.date | None = None
    if trade_date_raw:
        try:
            trade_date = datetime.date.fromisoformat(trade_date_raw)
        except ValueError:
            trade_date = None

    if trade_date is None:
        trade_date = datetime.datetime.now(datetime.UTC).date()

    if atr_source == "manual":
        if manual_atr_raw:
            try:
                manual_atr = Decimal(manual_atr_raw)
                if manual_atr > Decimal(0):
                    manual_session: Decimal | None = None
                    session_pct: Decimal | None = None
                    if manual_session_raw:
                        try:
                            manual_session = Decimal(manual_session_raw)
                            session_pct = (
                                manual_session / manual_atr
                            ) * Decimal(100)
                        except (InvalidOperation, ValueError):
                            pass

                    from tradefog.market.types import ATRContext

                    atr_ctx = ATRContext(
                        atr_value=manual_atr,
                        contributing_date=trade_date,
                        candles=[],
                        observed_session_range=manual_session,
                        session_range_percent=session_pct,
                        source="manual",
                        is_stale=False,
                    )
                    context["market_context"] = atr_ctx
                    context["reference_75_atr"] = manual_atr * Decimal("0.75")

                    if entry_raw and stop_raw:
                        try:
                            entry = Decimal(entry_raw)
                            stop = Decimal(stop_raw)
                            distance = abs(entry - stop)

                            reward_multiple = Decimal(3)
                            if strategy_id:
                                strat = TradingStrategy.objects.filter(
                                    pk=strategy_id,
                                    profile__owner=request.user,
                                    is_archived=False,
                                ).first()
                                if strat:
                                    reward_multiple = strat.reward_multiple

                            planned_move = distance * reward_multiple
                            context["planned_move"] = planned_move
                            move_pct = (planned_move / manual_atr) * Decimal(
                                100
                            )
                            context["planned_move_percent"] = move_pct
                            context["exceeds_75_atr"] = move_pct > Decimal(75)
                        except (InvalidOperation, ValueError):
                            pass
            except (InvalidOperation, ValueError):
                context["error"] = "Invalid manual ATR value."

        return render(
            request,
            "tradefog/trades/partials/market_context.html",
            context,
        )

    try:
        atr_ctx = fetch_bybit_atr_context(
            symbol=instrument.exec_symbol,
            product_kind=instrument.product,
            trade_date=trade_date,
        )
        context["market_context"] = atr_ctx

        # Serialize candles for ApexCharts
        chart_data = [
            {
                "date": candle.date.isoformat(),
                "open": str(candle.open),
                "high": str(candle.high),
                "low": str(candle.low),
                "close": str(candle.close),
            }
            for candle in atr_ctx.candles
        ]
        context["candles_json"] = json.dumps(chart_data)

        if atr_ctx.atr_value > Decimal(0):
            reference_75 = atr_ctx.atr_value * Decimal("0.75")
            context["reference_75_atr"] = reference_75

            # If entry and stop are present, calculate planned move comparison
            if entry_raw and stop_raw:
                try:
                    entry = Decimal(entry_raw)
                    stop = Decimal(stop_raw)
                    distance = abs(entry - stop)

                    reward_multiple = Decimal(3)
                    if strategy_id:
                        strat = TradingStrategy.objects.filter(
                            pk=strategy_id,
                            profile__owner=request.user,
                            is_archived=False,
                        ).first()
                        if strat:
                            reward_multiple = strat.reward_multiple

                    planned_move = distance * reward_multiple
                    context["planned_move"] = planned_move
                    move_pct = (planned_move / atr_ctx.atr_value) * Decimal(
                        100
                    )
                    context["planned_move_percent"] = move_pct
                    context["exceeds_75_atr"] = move_pct > Decimal(75)
                except (InvalidOperation, ValueError):
                    pass

    except MarketDataError as error:
        context["error"] = str(error)

    return render(
        request,
        "tradefog/trades/partials/market_context.html",
        context,
    )

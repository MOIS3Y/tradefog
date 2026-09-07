"""Lifecycle transition endpoints for journal trades."""

from __future__ import annotations

import datetime
from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect
from django.utils.translation import gettext_lazy as _
from django.views.decorators.http import require_POST

from tradefog.journal.forms.trades import TradeDecisionForm
from tradefog.journal.models.enums import ATRSource
from tradefog.journal.models.trades import Trade
from tradefog.journal.services import (
    cancel_trade,
    close_trade,
    open_trade,
    submit_trade,
)
from tradefog.journal.views.trades.workspace import extract_draft_context


@login_required
@require_POST
def trade_submit(request: HttpRequest, pk: int) -> HttpResponse:
    """Submit a draft trade and freeze its decision snapshot."""
    trade = get_object_or_404(
        Trade.objects.select_related(
            "profile", "strategy", "venue_instrument__pair"
        ),
        pk=pk,
        profile__owner=request.user,
    )

    form = TradeDecisionForm(
        request.POST,
        instance=trade,
        user=request.user,
        profile=trade.profile,
        strategy=trade.strategy,
    )
    if not form.is_valid():
        for errors in form.errors.values():
            for error in errors:
                messages.error(request, str(error))
        return redirect("journal:trade_workspace", pk=trade.pk)

    trade = form.save(commit=False)
    trade.draft_context = extract_draft_context(request.POST)
    trade.save()

    planned_entry = form.cleaned_data["planned_entry"]
    planned_stop = form.cleaned_data["planned_stop"]
    atr_source_choice = form.cleaned_data.get("atr_source_choice")

    atr_value = None
    atr_source = None
    atr_contributing_date = None

    if atr_source_choice == ATRSource.MANUAL:
        atr_value = form.cleaned_data.get("manual_atr_value")
        atr_source = ATRSource.MANUAL
    else:
        auto_atr_str = trade.draft_context.get("auto_atr_value")
        if auto_atr_str:
            try:
                atr_value = Decimal(auto_atr_str)
            except (InvalidOperation, ValueError):
                atr_value = None
        atr_source = str(trade.venue_instrument.venue.market_data_provider)
        date_str = trade.draft_context.get("atr_contributing_date")
        if date_str:
            try:
                atr_contributing_date = datetime.date.fromisoformat(date_str)
            except ValueError:
                atr_contributing_date = None

    try:
        _snapshot = submit_trade(
            trade,
            planned_entry=planned_entry,
            planned_stop=planned_stop,
            atr_value=atr_value,
            atr_source=atr_source,
            atr_contributing_date=atr_contributing_date,
        )
        messages.success(
            request, _("Trade submitted to pending entry successfully.")
        )
    except ValidationError as error:
        messages.error(
            request, error.messages[0] if error.messages else str(error)
        )

    return redirect("journal:trade_workspace", pk=trade.pk)


@login_required
@require_POST
def trade_open_action(request: HttpRequest, pk: int) -> HttpResponse:
    """Transition a pending trade to OPEN."""
    trade = get_object_or_404(
        Trade.objects.select_related(
            "profile", "strategy", "venue_instrument"
        ),
        pk=pk,
        profile__owner=request.user,
    )
    try:
        open_trade(trade)
        messages.success(request, _("Trade position marked as OPEN."))
    except ValidationError as error:
        messages.error(
            request, error.messages[0] if error.messages else str(error)
        )

    return redirect("journal:trade_workspace", pk=trade.pk)


@login_required
@require_POST
def trade_close_action(request: HttpRequest, pk: int) -> HttpResponse:
    """Transition an open trade to CLOSED with realized exit metrics."""
    trade = get_object_or_404(
        Trade.objects.select_related(
            "profile",
            "strategy",
            "venue_instrument__pair",
            "snapshot",
        ),
        pk=pk,
        profile__owner=request.user,
    )

    exit_price_str = request.POST.get("actual_exit_price", "").strip()
    commission_str = request.POST.get("total_commission", "").strip() or "0"
    funding_str = request.POST.get("funding_result", "").strip() or "0"

    try:
        actual_exit_price = Decimal(exit_price_str)
        total_commission = Decimal(commission_str)
        funding_result = Decimal(funding_str)
    except (InvalidOperation, ValueError):
        messages.error(request, _("Invalid numeric values provided."))
        return redirect("journal:trade_workspace", pk=trade.pk)

    try:
        close_trade(
            trade,
            actual_exit_price=actual_exit_price,
            total_commission=total_commission,
            funding_result=funding_result,
        )
        messages.success(request, _("Trade successfully closed."))
    except ValidationError as error:
        messages.error(
            request, error.messages[0] if error.messages else str(error)
        )

    return redirect("journal:trade_workspace", pk=trade.pk)


@login_required
@require_POST
def trade_cancel_action(request: HttpRequest, pk: int) -> HttpResponse:
    """Transition a pending or open trade to CANCELLED."""
    trade = get_object_or_404(
        Trade.objects.select_related(
            "profile", "strategy", "venue_instrument"
        ),
        pk=pk,
        profile__owner=request.user,
    )
    try:
        cancel_trade(trade)
        messages.success(request, _("Trade marked as CANCELLED."))
    except ValidationError as error:
        messages.error(
            request, error.messages[0] if error.messages else str(error)
        )

    return redirect("journal:trade_workspace", pk=trade.pk)

"""Focused domain services that read financial facts across tables.

Wallet reservations are derived state, not stored records: the amount an
active trade reserves on a wallet asset is read from its frozen snapshot.
"""

from __future__ import annotations

import datetime
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q, Sum
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from tradefog.journal.calculations import (
    calculate_position_plan,
    wallet_asset_status,
    wallet_balance,
)
from tradefog.journal.models import (
    StrategyCapital,
    TradingProfile,
    TradingStrategy,
    Venue,
    WalletAsset,
)
from tradefog.journal.models.enums import (
    ATRSource,
    Direction,
    StrategyStatus,
    TradeStatus,
    WalletAssetStatus,
    WalletOperationKind,
)
from tradefog.journal.models.trades import Trade, TradeSnapshot

_UNFINISHED_STATUSES = (
    TradeStatus.DRAFT.value,
    TradeStatus.PENDING_ENTRY.value,
    TradeStatus.OPEN.value,
)

_RESERVING_STATUSES = (
    TradeStatus.PENDING_ENTRY.value,
    TradeStatus.OPEN.value,
)


def strategy_has_active_trades_in_asset(
    strategy: TradingStrategy, asset_id: int
) -> bool:
    """Return whether any unfinished trade of a strategy settles in an asset.

    A draft, pending, or open trade all block archiving the allocation that
    backs the asset, because that trade would inherit the allocation's frozen
    capital. Closed and cancelled trades never block archiving.
    """
    return (
        Trade.objects.filter(
            strategy=strategy,
            status__in=_UNFINISHED_STATUSES,
        ).filter(
            Q(venue_instrument__settlement_asset_id=asset_id)
            | Q(
                venue_instrument__settlement_asset__isnull=True,
                venue_instrument__pair__quote_id=asset_id,
            )
        )
    ).exists()


def settlement_asset_ids(venue: Venue) -> set[int]:
    """Return the effective settlement asset ids of active venue instruments.

    Settlement is the instrument's explicit settlement asset (Perpetual
    Future) or its pair quote (Spot and Cash Equity).
    """
    instruments = venue.instruments.filter(is_active=True).select_related(
        "pair__quote"
    )
    return {
        instrument.settlement_asset_id
        if instrument.settlement_asset_id is not None
        else instrument.pair.quote_id
        for instrument in instruments
    }


def reserved_notional(profile: TradingProfile, asset_id: int) -> Decimal:
    """Return the capital reserved on one asset by active trades.

    Sums the frozen ``planned_notional`` of every pending or open trade of
    the profile whose instrument settles in ``asset_id``. Settlement is the
    instrument's explicit settlement asset, or its pair quote for Spot and
    Cash Equity.
    """
    trades = Trade.objects.filter(
        profile=profile,
        status__in=_RESERVING_STATUSES,
    ).filter(
        Q(venue_instrument__settlement_asset_id=asset_id)
        | Q(
            venue_instrument__settlement_asset__isnull=True,
            venue_instrument__pair__quote_id=asset_id,
        )
    )
    return trades.aggregate(total=Sum("snapshot__planned_notional"))[
        "total"
    ] or Decimal(0)


def wallet_asset_balance(asset: WalletAsset) -> Decimal:
    """Return the derived virtual balance of a wallet asset."""
    deposits = asset.operations.filter(
        kind=WalletOperationKind.DEPOSIT
    ).aggregate(total=Sum("amount"))["total"] or Decimal(0)
    withdrawals = asset.operations.filter(
        kind=WalletOperationKind.WITHDRAWAL
    ).aggregate(total=Sum("amount"))["total"] or Decimal(0)
    base_bal = wallet_balance(deposits, withdrawals)

    settlement_id = asset.venue_wallet_asset.asset_id
    closed_pnl = Trade.objects.filter(
        profile=asset.wallet.profile,
        status=TradeStatus.CLOSED,
    ).filter(
        Q(venue_instrument__settlement_asset_id=settlement_id)
        | Q(
            venue_instrument__settlement_asset__isnull=True,
            venue_instrument__pair__quote_id=settlement_id,
        )
    ).aggregate(total=Sum("realized_pnl"))["total"] or Decimal(0)
    return base_bal + closed_pnl


def update_wallet_asset_status(asset: WalletAsset) -> None:
    """Recalculate and update the advisory money-health status of an asset."""
    bal = wallet_asset_balance(asset)
    res = reserved_notional(
        asset.wallet.profile, asset.venue_wallet_asset.asset_id
    )
    worst_case = bal - res
    new_status = wallet_asset_status(bal, worst_case, asset.risk_stop_capital)
    if asset.status != new_status:
        asset.status = new_status
        asset.save(update_fields=["status"])


def update_strategy_status(strategy: TradingStrategy) -> None:
    """Recalculate and update strategy operational risk status."""
    allocations = list(
        strategy.capitals.filter(is_archived=False).select_related(
            "wallet_asset"
        )
    )
    if not allocations:
        return
    statuses = {alloc.wallet_asset.status for alloc in allocations}
    if WalletAssetStatus.RISK_STOPPED.value in statuses:
        new_status = StrategyStatus.RISK_STOPPED.value
    elif WalletAssetStatus.AT_RISK.value in statuses:
        new_status = StrategyStatus.AT_RISK.value
    else:
        new_status = StrategyStatus.ACTIVE.value
    if strategy.status != new_status:
        strategy.status = new_status
        strategy.save(update_fields=["status"])


@transaction.atomic
def submit_trade(
    trade: Trade,
    *,
    planned_entry: Decimal,
    planned_stop: Decimal,
    atr_value: Decimal | None = None,
    atr_source: ATRSource | str | None = None,
    atr_contributing_date: datetime.date | None = None,
    atr_observation_time: datetime.datetime | None = None,
    atr_stale: bool = False,
) -> TradeSnapshot:
    """Atomically freeze the decision context and transition trade to PENDING_ENTRY."""
    if trade.status != TradeStatus.DRAFT.value:
        raise ValidationError(
            _("Only trade drafts can be submitted."),
            code="invalid_status",
        )

    instrument = trade.venue_instrument
    settlement_id = instrument.settlement_asset_id or instrument.pair.quote_id
    capital_alloc = StrategyCapital.objects.filter(
        strategy=trade.strategy,
        wallet_asset__venue_wallet_asset__asset_id=settlement_id,
        is_archived=False,
    ).first()

    if not capital_alloc:
        raise ValidationError(
            _(
                "The selected strategy has no active capital allocation for the settlement asset."
            ),
            code="incompatible_settlement",
        )

    wallet_asset = capital_alloc.wallet_asset
    allocation_capital = capital_alloc.capital
    reward_multiple = trade.strategy.reward_multiple
    risk_percent = trade.strategy.risk_percent
    target_risk = allocation_capital * (risk_percent / Decimal(100))

    plan = calculate_position_plan(
        direction=trade.direction,
        entry=planned_entry,
        stop=planned_stop,
        target_risk_amount=target_risk,
        reward_multiple=reward_multiple,
        price_step=instrument.price_step,
        quantity_step=instrument.qty_step,
        minimum_quantity=instrument.min_qty,
        minimum_notional=instrument.min_notional,
    )

    bal = wallet_asset_balance(wallet_asset)
    res = reserved_notional(trade.profile, settlement_id)
    avail = bal - res

    if plan.notional > avail:
        raise ValidationError(
            _("Position value exceeds available wallet funds."),
            code="insufficient_wallet",
        )

    active_trades = Trade.objects.filter(
        profile=trade.profile,
        strategy=trade.strategy,
        status__in=_RESERVING_STATUSES,
    ).filter(
        Q(venue_instrument__settlement_asset_id=settlement_id)
        | Q(
            venue_instrument__settlement_asset__isnull=True,
            venue_instrument__pair__quote_id=settlement_id,
        )
    )
    already_reserved_risk = active_trades.aggregate(
        total=Sum("snapshot__planned_risk_amount")
    )["total"] or Decimal(0)
    remaining_risk_capacity = max(
        Decimal(0), allocation_capital - already_reserved_risk
    )

    deposit_floor_breach = False
    if wallet_asset.risk_stop_capital is not None:
        deposit_floor_breach = (avail - plan.notional) <= (
            wallet_asset.risk_stop_capital
        ) or bal <= wallet_asset.risk_stop_capital

    snapshot = TradeSnapshot.objects.create(
        trade=trade,
        planned_entry=planned_entry,
        planned_stop=planned_stop,
        planned_take_profit=plan.take_profit,
        quantity=plan.quantity,
        reward_multiple=reward_multiple,
        planned_risk_percent=risk_percent,
        planned_risk_amount=plan.planned_risk_amount,
        planned_notional=plan.notional,
        allocation_capital=allocation_capital,
        risk_stop_capital=wallet_asset.risk_stop_capital,
        already_reserved_risk=already_reserved_risk,
        remaining_risk_capacity=remaining_risk_capacity,
        deposit_floor_breach=deposit_floor_breach,
        wallet_balance=bal,
        wallet_reserved=res,
        wallet_available=avail,
        atr_value=atr_value,
        atr_source=atr_source,
        atr_contributing_date=atr_contributing_date,
        atr_observation_time=atr_observation_time,
        atr_stale=atr_stale,
    )

    trade.status = TradeStatus.PENDING_ENTRY.value
    trade.save(update_fields=["status"])

    update_wallet_asset_status(wallet_asset)
    update_strategy_status(trade.strategy)

    return snapshot


@transaction.atomic
def open_trade(trade: Trade) -> None:
    """Transition a pending trade to OPEN."""
    if trade.status != TradeStatus.PENDING_ENTRY.value:
        raise ValidationError(
            _("Only pending trades can be opened."),
            code="invalid_status",
        )
    trade.status = TradeStatus.OPEN.value
    trade.save(update_fields=["status"])


@transaction.atomic
def cancel_trade(trade: Trade) -> None:
    """Transition a pending or open trade to CANCELLED and release reservation."""
    if trade.status not in (
        TradeStatus.PENDING_ENTRY.value,
        TradeStatus.OPEN.value,
    ):
        raise ValidationError(
            _("Only pending or open trades can be cancelled."),
            code="invalid_status",
        )
    trade.status = TradeStatus.CANCELLED.value
    trade.save(update_fields=["status"])

    instrument = trade.venue_instrument
    settlement_id = instrument.settlement_asset_id or instrument.pair.quote_id
    wallet_asset = WalletAsset.objects.filter(
        wallet__profile=trade.profile,
        venue_wallet_asset__asset_id=settlement_id,
    ).first()
    if wallet_asset:
        update_wallet_asset_status(wallet_asset)
        update_strategy_status(trade.strategy)


@transaction.atomic
def close_trade(
    trade: Trade,
    *,
    actual_exit_price: Decimal,
    total_commission: Decimal = Decimal(0),
    funding_result: Decimal = Decimal(0),
) -> None:
    """Transition an open trade to CLOSED with realized P&L."""
    if trade.status != TradeStatus.OPEN.value:
        raise ValidationError(
            _("Only open trades can be closed."),
            code="invalid_status",
        )
    snapshot = getattr(trade, "snapshot", None)
    if not snapshot:
        raise ValidationError(
            _("Trade has no frozen decision snapshot."),
            code="missing_snapshot",
        )

    entry = snapshot.planned_entry
    qty = snapshot.quantity or Decimal(0)
    direction_sign = (
        Decimal(1) if trade.direction == Direction.LONG.value else Decimal(-1)
    )

    gross_pnl = (actual_exit_price - entry) * qty * direction_sign
    realized_pnl = gross_pnl - total_commission + funding_result

    trade.status = TradeStatus.CLOSED.value
    trade.actual_exit_price = actual_exit_price
    trade.total_commission = total_commission
    trade.funding_result = funding_result
    trade.realized_pnl = realized_pnl
    trade.save(
        update_fields=[
            "status",
            "actual_exit_price",
            "total_commission",
            "funding_result",
            "realized_pnl",
        ]
    )

    instrument = trade.venue_instrument
    settlement_id = instrument.settlement_asset_id or instrument.pair.quote_id
    wallet_asset = WalletAsset.objects.filter(
        wallet__profile=trade.profile,
        venue_wallet_asset__asset_id=settlement_id,
    ).first()
    if wallet_asset:
        update_wallet_asset_status(wallet_asset)
        update_strategy_status(trade.strategy)


@transaction.atomic
def set_trade_review_status(trade: Trade, completed: bool) -> None:
    """Set or clear the review completion timestamp on a closed trade."""
    if completed and trade.status != TradeStatus.CLOSED.value:
        raise ValidationError(
            _("Review can only be completed for closed trades."),
            code="not_closed",
        )
    trade.review_completed_at = timezone.now() if completed else None
    trade.save(update_fields=["review_completed_at"])

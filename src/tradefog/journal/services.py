"""Focused domain services that read financial facts across tables.

Wallet reservations are derived state, not stored records: the amount an
active trade reserves on a wallet asset is read from its frozen snapshot.
"""

from decimal import Decimal

from django.db.models import Q, Sum

from tradefog.journal.models import (
    TradingProfile,
    TradingStrategy,
    Venue,
)
from tradefog.journal.models.enums import TradeStatus
from tradefog.journal.models.trades import Trade

_UNFINISHED_STATUSES = (
    TradeStatus.DRAFT,
    TradeStatus.PENDING_ENTRY,
    TradeStatus.OPEN,
)

_RESERVING_STATUSES = (TradeStatus.PENDING_ENTRY, TradeStatus.OPEN)


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
    instruments = venue.instruments.filter(active=True).select_related(
        "pair__quote"
    )
    return {
        instrument.settlement_asset_id
        if instrument.settlement_asset_id is not None
        else instrument.pair.quote_id
        for instrument in instruments
    }


def reserved_notional(
    profile: TradingProfile, asset_id: int
) -> Decimal:
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
    return (
        trades.aggregate(total=Sum("snapshot__planned_notional"))["total"]
        or Decimal(0)
    )
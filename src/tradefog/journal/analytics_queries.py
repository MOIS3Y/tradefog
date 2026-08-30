"""Owner-scoped selection of closed trades for quality analytics."""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import cast

from tradefog.accounts.models import User
from tradefog.journal.analytics import ClosedTradeResult
from tradefog.journal.models import Trade


@dataclass(frozen=True, slots=True)
class AnalyticsFilters:
    """Validated filters applied to one analytics selection."""

    date_from: date | None = None
    date_to: date | None = None
    profile_id: int | None = None
    market_type: str | None = None
    trading_pair_id: int | None = None


def select_closed_trade_results(
    owner: User,
    filters: AnalyticsFilters,
) -> list[ClosedTradeResult]:
    """Return owner-scoped facts in deterministic analytical order."""
    trades = (
        Trade.objects.filter(
            profile__owner=owner,
            status=Trade.Status.CLOSED.value,
            result_r__isnull=False,
            reward_multiple__isnull=False,
        )
        .select_related(
            "profile",
            "trading_pair__asset",
            "profile__capital_asset",
        )
        .order_by("trade_date", "created_at", "id")
    )
    if filters.date_from is not None:
        trades = trades.filter(trade_date__gte=filters.date_from)
    if filters.date_to is not None:
        trades = trades.filter(trade_date__lte=filters.date_to)
    if filters.profile_id is not None:
        trades = trades.filter(profile_id=filters.profile_id)
    if filters.market_type:
        trades = trades.filter(profile__market_type=filters.market_type)
    if filters.trading_pair_id is not None:
        trades = trades.filter(trading_pair_id=filters.trading_pair_id)

    return [
        ClosedTradeResult(
            trade_id=trade.id,
            trade_date=trade.trade_date,
            profile_name=trade.profile.name,
            market_type=trade.profile.market_type,
            pair_symbol=trade.trading_pair.symbol,
            direction=trade.direction,
            result_r=cast(Decimal, trade.result_r),
            reward_multiple=cast(Decimal, trade.reward_multiple),
        )
        for trade in trades
    ]

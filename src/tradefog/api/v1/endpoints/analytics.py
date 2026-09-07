"""Owner-scoped exact-decimal analytics endpoints."""

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal, localcontext

from fastapi import APIRouter
from sqlalchemy import or_

from tradefog.api.dependencies import CurrentUserDependency, SessionDependency
from tradefog.api.errors import api_error
from tradefog.api.v1.schemas.analytics import (
    AnalyticsPeriod,
    AnalyticsResponse,
    DisciplineReferencePointResponse,
    ReferencePointResponse,
    StreakResponse,
    TrajectoryPointResponse,
)
from tradefog.db.models import (
    Trade,
    TradeSnapshot,
    TradingPair,
    TradingProfile,
    VenueInstrument,
)
from tradefog.db.scoping import owned_select
from tradefog.domain.analytics import (
    ClosedTradeResult,
    calculate_trade_analytics,
)
from tradefog.domain.enums import ProductKind, TradeStatus

router = APIRouter(prefix="/analytics", tags=["Analytics"])


@router.get("", response_model=AnalyticsResponse)
async def get_analytics(
    session: SessionDependency,
    user: CurrentUserDependency,
    date_from: date | None = None,
    date_to: date | None = None,
    period: AnalyticsPeriod = AnalyticsPeriod.ALL_TIME,
    profile_id: int | None = None,
    strategy_id: int | None = None,
    product: ProductKind | None = None,
    instrument_id: int | None = None,
    pair_id: int | None = None,
    settlement_asset_id: int | None = None,
) -> AnalyticsResponse:
    """Calculate quality metrics for a filtered cohort of closed trades."""
    if (
        period is AnalyticsPeriod.CUSTOM
        and date_from is None
        and date_to is None
    ):
        api_error(
            422,
            "invalid_date_range",
            "A custom period requires date_from or date_to",
        )
    if (
        period is not AnalyticsPeriod.CUSTOM
        and (date_from is not None or date_to is not None)
    ):
        api_error(
            422,
            "invalid_date_range",
            "Explicit dates require period=custom",
        )
    if period not in (AnalyticsPeriod.ALL_TIME, AnalyticsPeriod.CUSTOM):
        today = datetime.now(UTC).date()
        date_to = today
        if period is AnalyticsPeriod.LAST_30_DAYS:
            date_from = today - timedelta(days=29)
        elif period is AnalyticsPeriod.LAST_90_DAYS:
            date_from = today - timedelta(days=89)
        else:
            date_from = date(today.year, 1, 1)
    if date_from is not None and date_to is not None and date_from > date_to:
        api_error(422, "invalid_date_range", "date_from cannot follow date_to")

    statement = (
        owned_select(Trade, user.id)
        .add_columns(
            TradeSnapshot,
            TradingProfile.name,
            TradingPair.canonical_symbol,
            VenueInstrument.product,
        )
        .join(TradeSnapshot, TradeSnapshot.trade_id == Trade.id)
        .join(TradingProfile, TradingProfile.id == Trade.profile_id)
        .join(
            VenueInstrument,
            VenueInstrument.id == Trade.venue_instrument_id,
        )
        .join(TradingPair, TradingPair.id == VenueInstrument.pair_id)
        .where(
            Trade.status == TradeStatus.CLOSED,
            Trade.realized_pnl.is_not(None),
        )
        .order_by(Trade.trade_date, Trade.id)
    )
    if date_from is not None:
        statement = statement.where(Trade.trade_date >= date_from)
    if date_to is not None:
        statement = statement.where(Trade.trade_date <= date_to)
    if profile_id is not None:
        statement = statement.where(Trade.profile_id == profile_id)
    if strategy_id is not None:
        statement = statement.where(Trade.strategy_id == strategy_id)
    if product is not None:
        statement = statement.where(VenueInstrument.product == product)
    if instrument_id is not None:
        statement = statement.where(Trade.venue_instrument_id == instrument_id)
    if pair_id is not None:
        statement = statement.where(VenueInstrument.pair_id == pair_id)
    if settlement_asset_id is not None:
        statement = statement.where(
            or_(
                VenueInstrument.settlement_asset_id == settlement_asset_id,
                (
                    VenueInstrument.settlement_asset_id.is_(None)
                    & (TradingPair.quote_id == settlement_asset_id)
                ),
            )
        )

    closed_trades: list[ClosedTradeResult] = []
    excluded_trade_count = 0
    for trade, snapshot, profile_name, pair_symbol, market_type in (
        await session.execute(statement)
    ).all():
        risk = snapshot.planned_risk_amount
        reward = snapshot.reward_multiple
        if trade.realized_pnl is None or risk is None or risk <= 0:
            excluded_trade_count += 1
            continue
        with localcontext() as context:
            context.prec = 96
            result_r = trade.realized_pnl / risk
        closed_trades.append(
            ClosedTradeResult(
                trade_id=trade.id,
                trade_date=trade.trade_date,
                profile_name=profile_name,
                market_type=market_type.value,
                pair_symbol=pair_symbol,
                direction=trade.direction.value,
                result_r=result_r,
                reward_multiple=reward or Decimal(0),
            )
        )

    analytics = calculate_trade_analytics(closed_trades)
    trajectory = [
        TrajectoryPointResponse(
            sequence=point.sequence,
            trade_id=point.trade.trade_id,
            trade_date=point.trade.trade_date,
            profile_name=point.trade.profile_name,
            product=point.trade.market_type,
            pair_symbol=point.trade.pair_symbol,
            direction=point.trade.direction,
            result_r=point.trade.result_r,
            outcome=point.outcome,
            cumulative_result_r=point.cumulative_result_r,
            discipline_x=point.x,
            discipline_y=point.y,
        )
        for point in analytics.points
    ]
    reference = [ReferencePointResponse(sequence=0)]
    if analytics.closed_trade_count > 0:
        reference.append(
            ReferencePointResponse(sequence=analytics.closed_trade_count)
        )
    discipline_limit = max(analytics.final_x, analytics.final_y)
    discipline_reference = [
        DisciplineReferencePointResponse(x=Decimal(0), y=Decimal(0)),
    ]
    if discipline_limit > 0:
        discipline_reference.append(
            DisciplineReferencePointResponse(
                x=discipline_limit,
                y=discipline_limit,
            )
        )
    return AnalyticsResponse(
        closed_trade_count=analytics.closed_trade_count,
        excluded_trade_count=excluded_trade_count,
        win_count=analytics.win_count,
        loss_count=analytics.loss_count,
        break_even_count=analytics.break_even_count,
        win_rate_percent=analytics.win_rate * Decimal(100),
        net_result_r=analytics.net_result_r,
        average_result_r=analytics.average_result_r,
        average_win_r=analytics.average_win_r,
        average_loss_r=analytics.average_loss_r,
        gross_profit_r=analytics.gross_profit_r,
        gross_loss_r=analytics.gross_loss_r,
        profit_factor_r=analytics.profit_factor_r,
        expectancy_r=analytics.expectancy_r,
        maximum_drawdown_r=analytics.maximum_drawdown_r,
        current_streak=StreakResponse(
            outcome=analytics.current_streak.outcome,
            count=analytics.current_streak.count,
        ),
        maximum_winning_streak=analytics.maximum_winning_streak,
        maximum_losing_streak=analytics.maximum_losing_streak,
        trajectory=trajectory,
        break_even_reference=reference,
        discipline_break_even_reference=discipline_reference,
    )

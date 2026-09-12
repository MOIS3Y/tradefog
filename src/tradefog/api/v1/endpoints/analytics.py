"""Owner-scoped exact-decimal analytics endpoints."""

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal, localcontext

from fastapi import APIRouter

from tradefog.api.dependencies import CurrentUserDependency, SessionDependency
from tradefog.api.errors import api_error
from tradefog.api.v1.schemas.analytics import (
    AllocationMonetaryResponse,
    AnalyticsPeriod,
    AnalyticsResponse,
    DisciplineReferencePointResponse,
    MonetaryTrajectoryPointResponse,
    ReferencePointResponse,
    StreakResponse,
    TrajectoryPointResponse,
)
from tradefog.db.models import (
    StrategyCapital,
    Trade,
    TradeSnapshot,
    TradingAsset,
    TradingInstrument,
    TradingProfile,
    TradingStrategy,
)
from tradefog.db.scoping import owned_select
from tradefog.domain.analytics import (
    ClosedTradeResult,
    calculate_monetary_analytics,
    calculate_trade_analytics,
)
from tradefog.domain.enums import ProductKind, TradeStatus
from tradefog.services.journal import get_owned

router = APIRouter(prefix="/analytics", tags=["Overview · Analytics"])


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
    settlement_asset_id: int | None = None,
    strategy_capital_id: int | None = None,
) -> AnalyticsResponse:
    """Calculate quality metrics for a filtered cohort of closed trades.

    Explicit date bounds require period=custom and at least one bound;
    reversed bounds return 422, invalid_date_range. Preset periods use
    today's UTC date. Monetary results retain their asset denomination.
    """
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
    if period is not AnalyticsPeriod.CUSTOM and (
        date_from is not None or date_to is not None
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
    if strategy_capital_id is not None:
        allocation = await session.scalar(
            owned_select(StrategyCapital, user.id).where(
                StrategyCapital.id == strategy_capital_id,
            )
        )
        if allocation is None:
            api_error(404, "not_found", "StrategyCapital not found")

    statement = (
        owned_select(Trade, user.id)
        .add_columns(
            TradeSnapshot,
            TradingProfile.name,
            TradingInstrument.exec_symbol,
            TradingInstrument.product,
            TradingAsset.symbol,
        )
        .join(TradeSnapshot, TradeSnapshot.trade_id == Trade.id)
        .join(TradingProfile, TradingProfile.id == Trade.profile_id)
        .join(
            TradingInstrument,
            TradingInstrument.id == Trade.instrument_id,
        )
        .join(
            TradingAsset, TradingAsset.id == TradeSnapshot.settlement_asset_id
        )
        .where(
            Trade.status == TradeStatus.CLOSED,
            Trade.realized_pnl.is_not(None),
            Trade.closed_at.is_not(None),
        )
        .order_by(Trade.closed_at, Trade.id)
    )
    if date_from is not None:
        statement = statement.where(
            Trade.closed_at >= datetime.combine(date_from, datetime.min.time())
        )
    if date_to is not None:
        exclusive_end = datetime.combine(
            date_to + timedelta(days=1),
            datetime.min.time(),
        )
        statement = statement.where(Trade.closed_at < exclusive_end)
    if profile_id is not None:
        statement = statement.where(Trade.profile_id == profile_id)
    if strategy_id is not None:
        statement = statement.where(Trade.strategy_id == strategy_id)
    if product is not None:
        statement = statement.where(TradingInstrument.product == product)
    if instrument_id is not None:
        statement = statement.where(Trade.instrument_id == instrument_id)
    if settlement_asset_id is not None:
        statement = statement.where(
            TradeSnapshot.settlement_asset_id == settlement_asset_id,
        )
    if strategy_capital_id is not None:
        statement = statement.where(
            TradeSnapshot.strategy_capital_id == strategy_capital_id,
        )

    closed_trades: list[ClosedTradeResult] = []
    reviewed_trade_count = 0
    excluded_trade_count = 0
    profile_by_trade: dict[int, int] = {}
    for (
        trade,
        snapshot,
        profile_name,
        pair_symbol,
        market_type,
        settlement_symbol,
    ) in (await session.execute(statement)).all():
        profile_by_trade[trade.id] = trade.profile_id
        risk = snapshot.planned_risk_amount
        reward = snapshot.reward_multiple
        closed_at = trade.closed_at
        if (
            trade.realized_pnl is None
            or closed_at is None
            or risk is None
            or risk <= 0
        ):
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
                market_type=market_type,
                pair_symbol=pair_symbol,
                direction=trade.direction,
                result_r=result_r,
                reward_multiple=reward or Decimal(0),
                closed_at=closed_at,
                strategy_capital_id=snapshot.strategy_capital_id,
                settlement_asset_id=snapshot.settlement_asset_id,
                settlement_asset_symbol=settlement_symbol,
                allocation_capital=snapshot.allocation_capital or Decimal(0),
                realized_pnl=trade.realized_pnl,
                quality_rating=trade.quality_rating,
            )
        )
        if trade.review_completed_at is not None:
            reviewed_trade_count += 1

    analytics = calculate_trade_analytics(closed_trades)
    discipline_rewards = {trade.reward_multiple for trade in closed_trades}
    discipline_available = (
        strategy_capital_id is not None
        and len(discipline_rewards) == 1
        and next(iter(discipline_rewards)) >= 3
    )
    trajectory = [
        TrajectoryPointResponse(
            sequence=point.sequence,
            trade_id=point.trade.trade_id,
            profile_id=profile_by_trade[point.trade.trade_id],
            trade_date=point.trade.trade_date,
            closed_at=point.trade.closed_at,
            profile_name=point.trade.profile_name,
            product=point.trade.market_type,
            pair_symbol=point.trade.pair_symbol,
            direction=point.trade.direction,
            result_r=point.trade.result_r,
            outcome=point.outcome,
            cumulative_result_r=point.cumulative_result_r,
            discipline_x=point.x if discipline_available else None,
            discipline_y=point.y if discipline_available else None,
        )
        for point in analytics.points
    ]
    reference = [ReferencePointResponse(sequence=0)]
    if analytics.closed_trade_count > 0:
        reference.append(
            ReferencePointResponse(sequence=analytics.closed_trade_count)
        )
    discipline_reference: list[DisciplineReferencePointResponse] = []
    discipline_reward: Decimal | None = None
    if discipline_available:
        discipline_reward = closed_trades[0].reward_multiple
        discipline_reference.append(
            DisciplineReferencePointResponse(x=Decimal(0), y=Decimal(0))
        )
        discipline_limit = max(
            analytics.final_x,
            analytics.final_y * discipline_reward,
        )
    else:
        discipline_limit = Decimal(0)
    if discipline_reward is not None and discipline_limit > 0:
        discipline_reference.append(
            DisciplineReferencePointResponse(
                x=discipline_limit,
                y=discipline_limit / discipline_reward,
            )
        )
    monetary = [
        AllocationMonetaryResponse(
            strategy_capital_id=item.strategy_capital_id,
            settlement_asset_id=item.settlement_asset_id,
            settlement_asset_symbol=item.settlement_asset_symbol,
            allocation_capital=item.allocation_capital,
            trade_count=item.trade_count,
            gross_profit=item.gross_profit,
            gross_loss=item.gross_loss,
            net_pnl=item.net_pnl,
            allocation_return_percent=item.allocation_return_percent,
            trajectory=[
                MonetaryTrajectoryPointResponse(
                    sequence=point.sequence,
                    trade_id=point.trade_id,
                    profile_id=profile_by_trade[point.trade_id],
                    closed_at=point.closed_at,
                    realized_pnl=point.realized_pnl,
                    cumulative_pnl=point.cumulative_pnl,
                )
                for point in item.points
            ],
        )
        for item in calculate_monetary_analytics(closed_trades)
    ]
    return AnalyticsResponse(
        closed_trade_count=analytics.closed_trade_count,
        reviewed_trade_count=reviewed_trade_count,
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
        average_quality_rating=analytics.average_quality_rating,
        trajectory=trajectory,
        break_even_reference=reference,
        discipline_available=discipline_available,
        discipline_reward_multiple=(
            int(discipline_reward) if discipline_reward is not None else None
        ),
        discipline_break_even_reference=discipline_reference,
        monetary=monetary,
    )


profile_router = APIRouter(
    prefix="/profiles/{profile_id}/analytics", tags=["Profiles · Analytics"]
)


@profile_router.get("", response_model=AnalyticsResponse)
async def get_profile_analytics(
    profile_id: int,
    session: SessionDependency,
    user: CurrentUserDependency,
    date_from: date | None = None,
    date_to: date | None = None,
    period: AnalyticsPeriod = AnalyticsPeriod.ALL_TIME,
    strategy_id: int | None = None,
    product: ProductKind | None = None,
    instrument_id: int | None = None,
    settlement_asset_id: int | None = None,
    strategy_capital_id: int | None = None,
) -> AnalyticsResponse:
    """Calculate the existing analytics within an accessible profile."""
    await get_owned(session, TradingProfile, profile_id, user.id)
    if strategy_capital_id is not None:
        allocation = await get_owned(
            session, StrategyCapital, strategy_capital_id, user.id
        )
        strategy = await get_owned(
            session, TradingStrategy, allocation.strategy_id, user.id
        )
        if strategy.profile_id != profile_id:
            api_error(404, "not_found", "StrategyCapital not found")
    return await get_analytics(
        session,
        user,
        date_from,
        date_to,
        period,
        profile_id,
        strategy_id,
        product,
        instrument_id,
        settlement_asset_id,
        strategy_capital_id,
    )

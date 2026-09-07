"""Owner-scoped trade workspace, volatility and lifecycle endpoints."""

from datetime import UTC, datetime
from decimal import Decimal, localcontext

from fastapi import APIRouter, status
from pydantic import ValidationError
from sqlalchemy import select
from starlette.concurrency import run_in_threadpool

from tradefog.api.dependencies import CurrentUserDependency, SessionDependency
from tradefog.api.errors import api_error, conflict, not_found
from tradefog.api.v1.schemas.trades import (
    ATRRequest,
    ATRResponse,
    CandleResponse,
    ChecklistResponse,
    ChecklistWrite,
    SnapshotResponse,
    TradeClose,
    TradeCreate,
    TradePatch,
    TradePlanRequest,
    TradePlanResponse,
    TradeResponse,
    TradeReview,
    TradeSubmit,
)
from tradefog.db.models import (
    Trade,
    TradeSnapshot,
    TradingProfile,
    Venue,
    VenueInstrument,
)
from tradefog.db.scoping import owned_select
from tradefog.domain.checklists import (
    ChecklistAnswers,
    calculate_checklist_assessment,
)
from tradefog.domain.enums import ATRSource, TradeStatus
from tradefog.market.service import fetch_atr_context
from tradefog.market.types import MarketDataError
from tradefog.services.journal import get_owned, recompute_wallet_asset
from tradefog.services.trades import (
    ATRDecisionContext,
    SubmissionContext,
    atr_from_context,
    checklist_payload,
    prepare_submission,
    settlement_allocation,
    stored_decimal,
    submit_trade,
    validate_trade_identity,
)

router = APIRouter(prefix="/trades", tags=["Trades"])


def store_draft_section(
    trade: Trade,
    name: str,
    value: dict[str, object],
) -> None:
    """Replace a JSON section so SQLAlchemy reliably detects the mutation."""
    context = dict(trade.draft_context)
    context[name] = value
    trade.draft_context = context


def atr_response(context: ATRDecisionContext) -> ATRResponse:
    """Convert persisted ATR facts into their transport representation."""
    return ATRResponse(
        value=context.value,
        source=context.source,
        contributing_date=context.contributing_date,
        observation_time=context.observation_time,
        stale=context.stale,
        observed_session_range=context.observed_session_range,
        session_range_percent=context.session_range_percent,
    )


def saved_plan(trade: Trade) -> TradePlanRequest | None:
    """Deserialize the saved plan and reject malformed draft JSON."""
    raw = trade.draft_context.get("plan")
    if raw is None:
        return None
    if not isinstance(raw, dict):
        api_error(422, "invalid_draft_context", "Saved trade plan is invalid")
    try:
        return TradePlanRequest.model_validate(raw)
    except ValidationError:
        api_error(422, "invalid_draft_context", "Saved trade plan is invalid")


async def trade_response(
    session: SessionDependency,
    trade: Trade,
) -> TradeResponse:
    """Build a complete trade response with explicitly loaded history."""
    snapshot = await session.scalar(
        select(TradeSnapshot).where(TradeSnapshot.trade_id == trade.id)
    )
    atr = atr_from_context(trade)
    return TradeResponse(
        id=trade.id,
        profile_id=trade.profile_id,
        strategy_id=trade.strategy_id,
        venue_instrument_id=trade.venue_instrument_id,
        trade_date=trade.trade_date,
        status=trade.status,
        direction=trade.direction,
        description_markdown=trade.description_markdown,
        review_completed_at=trade.review_completed_at,
        realized_pnl=trade.realized_pnl,
        actual_exit_price=trade.actual_exit_price,
        total_commission=trade.total_commission,
        funding_result=trade.funding_result,
        created_at=trade.created_at,
        checklist=ChecklistResponse.model_validate(checklist_payload(trade)),
        plan=saved_plan(trade),
        atr=atr_response(atr) if atr is not None else None,
        snapshot=(
            SnapshotResponse.model_validate(snapshot)
            if snapshot is not None
            else None
        ),
    )


def plan_response(
    entry: Decimal,
    stop: Decimal,
    context: SubmissionContext,
) -> TradePlanResponse:
    """Serialize a validated, non-persisted position plan."""
    atr_percent: Decimal | None = None
    fits_atr_limit: bool | None = None
    if context.atr is not None and context.atr.value > 0:
        with localcontext() as decimal_context:
            decimal_context.prec = 96
            atr_percent = stored_decimal(
                context.plan.take_profit_distance
                / context.atr.value
                * Decimal(100),
            )
        fits_atr_limit = atr_percent <= Decimal(75)
    return TradePlanResponse(
        planned_entry=entry,
        planned_stop=stop,
        planned_take_profit=stored_decimal(context.plan.take_profit),
        quantity=stored_decimal(context.plan.quantity),
        reward_multiple=context.strategy.reward_multiple,
        planned_risk_percent=context.strategy.risk_percent,
        planned_risk_amount=stored_decimal(
            context.plan.planned_risk_amount,
        ),
        planned_notional=stored_decimal(context.plan.notional),
        allocation_capital=context.allocation.capital,
        already_reserved_risk=stored_decimal(
            context.already_reserved_risk,
        ),
        remaining_risk_capacity=stored_decimal(
            context.remaining_risk_after_plan,
        ),
        deposit_floor_breach=(
            context.wallet_asset.risk_stop_capital is not None
            and context.balance <= context.wallet_asset.risk_stop_capital
        ),
        wallet_balance=stored_decimal(context.balance),
        wallet_reserved=stored_decimal(context.reserved_notional),
        wallet_available=stored_decimal(context.available),
        atr_value=context.atr.value if context.atr else None,
        take_profit_atr_percent=atr_percent,
        fits_atr_limit=fits_atr_limit,
    )


@router.get("", response_model=list[TradeResponse])
async def list_trades(
    session: SessionDependency,
    user: CurrentUserDependency,
    profile_id: int | None = None,
    strategy_id: int | None = None,
    trade_status: TradeStatus | None = None,
) -> list[TradeResponse]:
    """List authenticated journal trades with optional cohort filters."""
    statement = owned_select(Trade, user.id).order_by(
        Trade.trade_date.desc(), Trade.id.desc(),
    )
    if profile_id is not None:
        statement = statement.where(Trade.profile_id == profile_id)
    if strategy_id is not None:
        statement = statement.where(Trade.strategy_id == strategy_id)
    if trade_status is not None:
        statement = statement.where(Trade.status == trade_status)
    trades = (await session.scalars(statement)).all()
    return [await trade_response(session, trade) for trade in trades]


@router.post(
    "", response_model=TradeResponse, status_code=status.HTTP_201_CREATED,
)
async def create_trade(
    request: TradeCreate,
    session: SessionDependency,
    user: CurrentUserDependency,
) -> TradeResponse:
    """Create an editable draft after validating its profile references."""
    profile = await get_owned(
        session, TradingProfile, request.profile_id, user.id, for_update=True,
    )
    if profile.is_archived:
        conflict("Archived profiles cannot accept new trades")
    await validate_trade_identity(
        session,
        profile,
        request.strategy_id,
        request.venue_instrument_id,
        user.id,
    )
    trade = Trade(
        profile_id=profile.id,
        strategy_id=request.strategy_id,
        venue_instrument_id=request.venue_instrument_id,
        trade_date=request.trade_date,
        status=TradeStatus.DRAFT,
        direction=request.direction,
        draft_context={},
        description_markdown=request.description_markdown,
    )
    session.add(trade)
    await session.flush()
    return await trade_response(session, trade)


@router.get("/{trade_id}", response_model=TradeResponse)
async def get_trade(
    trade_id: int,
    session: SessionDependency,
    user: CurrentUserDependency,
) -> TradeResponse:
    """Return the complete workspace for one owned trade."""
    trade = await get_owned(session, Trade, trade_id, user.id)
    return await trade_response(session, trade)


@router.delete("/{trade_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_trade(
    trade_id: int,
    session: SessionDependency,
    user: CurrentUserDependency,
) -> None:
    """Permanently remove a draft that has never created immutable history."""
    trade = await get_owned(
        session, Trade, trade_id, user.id, for_update=True,
    )
    if trade.status != TradeStatus.DRAFT:
        conflict("Only a draft trade can be deleted")
    await session.delete(trade)
    await session.flush()


@router.patch("/{trade_id}", response_model=TradeResponse)
async def update_trade(
    trade_id: int,
    request: TradePatch,
    session: SessionDependency,
    user: CurrentUserDependency,
) -> TradeResponse:
    """Edit draft identity and universally editable date or Markdown notes."""
    trade = await get_owned(
        session, Trade, trade_id, user.id, for_update=True,
    )
    values = request.model_dump(exclude_unset=True)
    draft_only = {"strategy_id", "venue_instrument_id", "direction"}
    if trade.status != TradeStatus.DRAFT and draft_only & values.keys():
        conflict("Submitted trade identity is immutable")
    if draft_only & values.keys():
        profile = await get_owned(
            session, TradingProfile, trade.profile_id, user.id,
        )
        await validate_trade_identity(
            session,
            profile,
            values.get("strategy_id", trade.strategy_id),
            values.get("venue_instrument_id", trade.venue_instrument_id),
            user.id,
        )
    for field, value in values.items():
        setattr(trade, field, value)
    await session.flush()
    return await trade_response(session, trade)


@router.put("/{trade_id}/checklist", response_model=ChecklistResponse)
async def update_checklist(
    trade_id: int,
    request: ChecklistWrite,
    session: SessionDependency,
    user: CurrentUserDependency,
) -> ChecklistResponse:
    """Replace and assess the four directional answers on a draft trade."""
    trade = await get_owned(
        session, Trade, trade_id, user.id, for_update=True,
    )
    if trade.status != TradeStatus.DRAFT:
        conflict("Checklist is locked after trade submission")
    answers = request.model_dump(mode="json")
    store_draft_section(trade, "checklist", answers)
    assessment = calculate_checklist_assessment(
        ChecklistAnswers(**answers),
        trade_direction=trade.direction.value,
    )
    await session.flush()
    return ChecklistResponse(
        **request.model_dump(),
        score=assessment.score,
        direction=assessment.direction,
        completeness=assessment.completeness,
        answered_count=assessment.answered_count,
        total_count=assessment.total_count,
        gauge_position=assessment.gauge_position,
        trend_relationship=assessment.trend_relationship,
        agrees_with_trade=assessment.agrees_with_trade,
    )


@router.post("/{trade_id}/atr", response_model=ATRResponse)
async def refresh_atr(
    trade_id: int,
    request: ATRRequest,
    session: SessionDependency,
    user: CurrentUserDependency,
) -> ATRResponse:
    """Fetch ATR on demand or persist a manual fallback in draft context."""
    trade = await get_owned(session, Trade, trade_id, user.id)
    if trade.status != TradeStatus.DRAFT:
        conflict("ATR context is locked after trade submission")
    if request.value is not None:
        if (
            request.contributing_date is not None
            and request.contributing_date > trade.trade_date
        ):
            api_error(
                422,
                "invalid_atr_date",
                "ATR contributing date cannot follow the trade date",
            )
        response = ATRResponse(
            value=request.value,
            source=ATRSource.MANUAL,
            contributing_date=request.contributing_date or trade.trade_date,
            observation_time=datetime.now(UTC),
            stale=request.stale,
        )
    else:
        instrument = await session.get(
            VenueInstrument, trade.venue_instrument_id,
        )
        profile = await get_owned(
            session, TradingProfile, trade.profile_id, user.id,
        )
        venue = await session.get(Venue, profile.venue_id)
        if instrument is None or venue is None:
            not_found("Trade market context")
        if venue.market_data_provider.value == "none":
            api_error(
                422, "manual_atr_required",
                "Venue has no automatic market data provider",
            )
        try:
            context = await run_in_threadpool(
                fetch_atr_context,
                venue.market_data_provider.value,
                instrument.exec_symbol,
                product_kind=instrument.product.value,
                trade_date=trade.trade_date,
            )
        except MarketDataError as error:
            api_error(503, "market_data_unavailable", str(error))
        response = ATRResponse(
            value=context.atr_value,
            source=ATRSource.AUTO,
            contributing_date=context.contributing_date,
            observation_time=datetime.now(UTC),
            stale=context.is_stale,
            observed_session_range=context.observed_session_range,
            session_range_percent=context.session_range_percent,
            candles=[CandleResponse(
                date=candle.date,
                open=candle.open,
                high=candle.high,
                low=candle.low,
                close=candle.close,
            ) for candle in context.candles],
        )
    locked_trade = await session.scalar(
        owned_select(Trade, user.id)
        .where(Trade.id == trade_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if locked_trade is None:
        not_found("Trade")
    if locked_trade.status != TradeStatus.DRAFT:
        conflict("ATR context is locked after trade submission")
    store_draft_section(locked_trade, "atr", {
        "value": str(response.value),
        "source": response.source.value,
        "contributing_date": response.contributing_date.isoformat(),
        "observation_time": response.observation_time.isoformat(),
        "stale": response.stale,
        "observed_session_range": (
            str(response.observed_session_range)
            if response.observed_session_range is not None else None
        ),
        "session_range_percent": (
            str(response.session_range_percent)
            if response.session_range_percent is not None else None
        ),
    })
    await session.flush()
    return response


@router.post("/{trade_id}/plan", response_model=TradePlanResponse)
async def preview_trade_plan(
    trade_id: int,
    request: TradePlanRequest,
    session: SessionDependency,
    user: CurrentUserDependency,
) -> TradePlanResponse:
    """Calculate an executable plan without persisting a snapshot."""
    trade = await get_owned(
        session, Trade, trade_id, user.id, for_update=True,
    )
    context = await prepare_submission(
        session,
        trade,
        request.planned_entry,
        request.planned_stop,
    )
    return plan_response(
        request.planned_entry,
        request.planned_stop,
        context,
    )


@router.put("/{trade_id}/plan", response_model=TradeResponse)
async def save_trade_plan(
    trade_id: int,
    request: TradePlanRequest,
    session: SessionDependency,
    user: CurrentUserDependency,
) -> TradeResponse:
    """Persist editable entry and stop values in a draft context."""
    trade = await get_owned(
        session, Trade, trade_id, user.id, for_update=True,
    )
    if trade.status != TradeStatus.DRAFT:
        conflict("Plan is locked after trade submission")
    store_draft_section(trade, "plan", request.model_dump(mode="json"))
    await session.flush()
    return await trade_response(session, trade)


@router.post("/{trade_id}/submit", response_model=TradeResponse)
async def submit_draft(
    trade_id: int,
    request: TradeSubmit,
    session: SessionDependency,
    user: CurrentUserDependency,
) -> TradeResponse:
    """Create one immutable snapshot and reserve wallet capital atomically."""
    trade = await session.scalar(
        owned_select(Trade, user.id)
        .where(Trade.id == trade_id)
        .with_for_update()
    )
    if trade is None:
        not_found("Trade")
    plan = saved_plan(trade)
    if plan is None:
        api_error(
            422,
            "missing_draft_plan",
            "Save planned entry and stop before submitting the trade",
        )
    await submit_trade(
        session,
        trade,
        request.status,
        plan.planned_entry,
        plan.planned_stop,
    )
    return await trade_response(session, trade)


@router.post("/{trade_id}/open", response_model=TradeResponse)
async def open_trade(
    trade_id: int,
    session: SessionDependency,
    user: CurrentUserDependency,
) -> TradeResponse:
    """Mark a pending external order as filled and open."""
    trade = await get_owned(
        session, Trade, trade_id, user.id, for_update=True,
    )
    if trade.status != TradeStatus.PENDING_ENTRY:
        conflict("Only a pending trade can be opened")
    trade.status = TradeStatus.OPEN
    await session.flush()
    return await trade_response(session, trade)


@router.post("/{trade_id}/cancel", response_model=TradeResponse)
async def cancel_trade(
    trade_id: int,
    session: SessionDependency,
    user: CurrentUserDependency,
) -> TradeResponse:
    """Cancel a draft, pending or open trade and release derived reservation."""
    trade = await get_owned(
        session, Trade, trade_id, user.id, for_update=True,
    )
    if trade.status not in (
        TradeStatus.DRAFT,
        TradeStatus.PENDING_ENTRY,
        TradeStatus.OPEN,
    ):
        conflict("Trade cannot be cancelled from its current state")
    trade.status = TradeStatus.CANCELLED
    await session.flush()
    return await trade_response(session, trade)


@router.post("/{trade_id}/close", response_model=TradeResponse)
async def close_trade(
    trade_id: int,
    request: TradeClose,
    session: SessionDependency,
    user: CurrentUserDependency,
) -> TradeResponse:
    """Close an open trade, release reservation and add realized P&L."""
    trade = await get_owned(
        session, Trade, trade_id, user.id, for_update=True,
    )
    if trade.status != TradeStatus.OPEN:
        conflict("Only an open trade can be closed")
    _allocation, wallet_asset = await settlement_allocation(
        session, trade, active_only=False,
    )
    trade.status = TradeStatus.CLOSED
    trade.realized_pnl = request.realized_pnl
    trade.actual_exit_price = request.actual_exit_price
    trade.total_commission = request.total_commission
    trade.funding_result = request.funding_result
    await session.flush()
    await recompute_wallet_asset(session, wallet_asset)
    await session.flush()
    return await trade_response(session, trade)


@router.put("/{trade_id}/review", response_model=TradeResponse)
async def review_trade(
    trade_id: int,
    request: TradeReview,
    session: SessionDependency,
    user: CurrentUserDependency,
) -> TradeResponse:
    """Set review completion time on a closed trade."""
    trade = await get_owned(
        session, Trade, trade_id, user.id, for_update=True,
    )
    if trade.status != TradeStatus.CLOSED:
        conflict("Only a closed trade can be reviewed")
    trade.review_completed_at = (
        datetime.now(UTC).replace(tzinfo=None) if request.completed else None
    )
    await session.flush()
    return await trade_response(session, trade)

"""Owner-scoped trade workspace, volatility and lifecycle endpoints."""

from datetime import UTC, datetime
from decimal import Decimal, localcontext
from typing import Annotated

from fastapi import APIRouter, Query, status
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from tradefog.api.dependencies import CurrentUserDependency, SessionDependency
from tradefog.api.errors import api_error, conflict, not_found
from tradefog.api.v1.endpoints.venues import MarketDependency
from tradefog.api.v1.schemas.pagination import Page
from tradefog.api.v1.schemas.trades import (
    ATRRequest,
    ATRResponse,
    CandleResponse,
    ChecklistResponse,
    ChecklistWrite,
    PreparationResponse,
    ProfileTradeListQuery,
    ReservationResponse,
    SnapshotResponse,
    StoredReservationResponse,
    TradeClose,
    TradeCreate,
    TradeListItem,
    TradeListQuery,
    TradePatch,
    TradePlanningContextResponse,
    TradePlanRequest,
    TradePlanResponse,
    TradePlanSave,
    TradeResponse,
    TradeReview,
    TradeSubmit,
)
from tradefog.db.models import (
    Attachment,
    StrategyCapital,
    Trade,
    TradePreparation,
    TradeReservation,
    TradeSnapshot,
    TradingAsset,
    TradingInstrument,
    TradingProfile,
    TradingStrategy,
)
from tradefog.db.scoping import owned_select
from tradefog.domain.checklists import (
    ChecklistAnswers,
    calculate_checklist_assessment,
)
from tradefog.domain.enums import ATRSource, TradeStatus
from tradefog.services.journal import (
    get_owned,
    get_profile_trade,
    recompute_wallet_asset,
    wallet_balance,
    wallet_reserved,
)
from tradefog.services.pagination import paginate, search_text
from tradefog.services.trades import (
    ATRDecisionContext,
    SubmissionContext,
    atr_from_context,
    checklist_payload,
    prepare_planning_context,
    prepare_submission,
    stored_decimal,
    submit_trade,
    validate_trade_identity,
)

router = APIRouter(prefix="/profiles/{profile_id}/trades")
overview_router = APIRouter(prefix="/trades", tags=["Overview · Trades"])


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
    """Read optional typed entry and stop inputs."""
    p = trade.preparation
    if p.planned_entry is None or p.planned_stop is None:
        return None
    return TradePlanRequest(
        planned_entry=p.planned_entry, planned_stop=p.planned_stop
    )


async def trade_response(
    session: SessionDependency,
    trade: Trade,
) -> TradeResponse:
    """Build a complete trade response with explicitly loaded history."""
    snapshot = await session.scalar(
        select(TradeSnapshot).where(TradeSnapshot.trade_id == trade.id)
    )
    atr = atr_from_context(trade)
    reservations = (
        await session.scalars(
            select(TradeReservation)
            .join(TradeSnapshot)
            .where(TradeSnapshot.trade_id == trade.id)
        )
    ).all()
    return TradeResponse(
        id=trade.id,
        profile_id=trade.profile_id,
        preparation=PreparationResponse.model_validate(trade.preparation),
        reservations=[
            StoredReservationResponse.model_validate(row)
            for row in reservations
        ],
        strategy_id=trade.strategy_id,
        instrument_id=trade.instrument_id,
        trade_date=trade.trade_date,
        status=trade.status,
        direction=trade.direction,
        description_markdown=trade.description_markdown,
        quality_rating=trade.quality_rating,
        review_completed_at=trade.review_completed_at,
        realized_pnl=trade.realized_pnl,
        actual_exit_price=trade.actual_exit_price,
        total_commission=trade.total_commission,
        funding_result=trade.funding_result,
        submitted_at=trade.submitted_at,
        opened_at=trade.opened_at,
        closed_at=trade.closed_at,
        cancelled_at=trade.cancelled_at,
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
        stop_distance=stored_decimal(context.plan.distance),
        take_profit_distance=stored_decimal(
            context.plan.take_profit_distance,
        ),
        quantity=stored_decimal(context.plan.quantity),
        reward_multiple=int(context.strategy.reward_multiple),
        planned_risk_percent=context.strategy.risk_percent,
        target_risk_amount=context.target_risk_amount,
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
        capital_remaining=stored_decimal(
            context.available - context.reservations[0].amount,
        ),
        capital_sufficient=(
            all(row.amount <= row.available for row in context.reservations)
            and context.target_risk_amount <= context.remaining_risk_capacity
        ),
        atr_value=context.atr.value if context.atr else None,
        reservations=[
            ReservationResponse(
                asset_id=row.asset_id,
                purpose=row.purpose,
                amount=row.amount,
                available=row.available,
            )
            for row in context.reservations
        ],
        take_profit_atr_percent=atr_percent,
        fits_atr_limit=fits_atr_limit,
    )


@overview_router.get("", response_model=Page[TradeListItem])
async def list_trades(
    session: SessionDependency,
    user: CurrentUserDependency,
    query: Annotated[TradeListQuery, Query()],
) -> Page[TradeListItem]:
    """List authenticated journal trades with optional cohort filters."""
    statement = (
        owned_select(Trade, user.id)
        .join(
            TradingProfile,
            Trade.profile_id == TradingProfile.id,
        )
        .join(
            TradingStrategy,
            Trade.strategy_id == TradingStrategy.id,
        )
        .join(
            TradingInstrument,
            Trade.instrument_id == TradingInstrument.id,
        )
        .options(
            selectinload(Trade.profile),
            selectinload(Trade.strategy),
            selectinload(Trade.instrument).selectinload(
                TradingInstrument.quote_asset
            ),
            selectinload(Trade.instrument).selectinload(
                TradingInstrument.base_asset
            ),
            selectinload(Trade.instrument).selectinload(
                TradingInstrument.settlement_asset,
            ),
        )
    )
    for column, value in (
        (Trade.profile_id, query.profile_id),
        (Trade.strategy_id, query.strategy_id),
        (Trade.status, query.trade_status),
        (Trade.direction, query.direction),
    ):
        if value is not None:
            statement = statement.where(column == value)
    if query.date_from:
        statement = statement.where(Trade.trade_date >= query.date_from)
    if query.date_to:
        statement = statement.where(Trade.trade_date <= query.date_to)
    if query.review == "reviewed":
        statement = statement.where(Trade.review_completed_at.is_not(None))
    elif query.review == "unreviewed":
        statement = statement.where(
            Trade.status == TradeStatus.CLOSED,
            Trade.review_completed_at.is_(None),
        )
    if query.rated is not None:
        statement = statement.where(
            Trade.quality_rating.is_not(None)
            if query.rated
            else Trade.quality_rating.is_(None),
        )
    if query.q.strip():
        statement = statement.where(
            search_text(
                [
                    TradingInstrument.exec_symbol,
                    TradingInstrument.exec_symbol,
                    TradingProfile.name,
                    TradingStrategy.name,
                ]
            ).icontains(query.q.strip(), autoescape=True)
        )
    items, total = await paginate(
        session,
        statement,
        query,
        {
            "id": Trade.id,
            "trade_date": Trade.trade_date,
            "instrument": TradingInstrument.exec_symbol,
            "profile": TradingProfile.name,
            "strategy": TradingStrategy.name,
            "direction": Trade.direction,
            "status": Trade.status,
            "quality_rating": Trade.quality_rating,
            "review_completed_at": Trade.review_completed_at,
        },
        "id",
        Trade.id.desc()
        if query.sort == "trade_date" and query.order == "desc"
        else Trade.id,
    )
    rows = []
    for trade in items:
        instrument = trade.instrument
        settlement = instrument.settlement_asset
        rows.append(
            TradeListItem(
                id=trade.id,
                profile_id=trade.profile_id,
                profile_name=trade.profile.name,
                strategy_id=trade.strategy_id,
                strategy_name=trade.strategy.name,
                instrument_id=instrument.id,
                exec_symbol=instrument.exec_symbol,
                pair_symbol=f"{instrument.base_asset.symbol}/{instrument.quote_asset.symbol}",
                settlement_symbol=settlement.symbol,
                trade_date=trade.trade_date,
                direction=trade.direction,
                status=trade.status,
                realized_pnl=trade.realized_pnl,
                quality_rating=trade.quality_rating,
                review_completed_at=trade.review_completed_at,
            )
        )
    return Page(
        items=rows, total=total, page=query.page, page_size=query.page_size
    )


@router.get("", response_model=Page[TradeListItem], tags=["Profiles · Trades"])
async def list_profile_trades(
    profile_id: int,
    session: SessionDependency,
    user: CurrentUserDependency,
    query: Annotated[ProfileTradeListQuery, Query()],
) -> Page[TradeListItem]:
    """List trades only after resolving the requested owned profile."""
    await get_owned(session, TradingProfile, profile_id, user.id)
    return await list_trades(
        session,
        user,
        TradeListQuery(**query.model_dump(), profile_id=profile_id),
    )


@router.post(
    "",
    response_model=TradeResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["Profiles · Trades"],
)
async def create_trade(
    profile_id: int,
    request: TradeCreate,
    session: SessionDependency,
    user: CurrentUserDependency,
) -> TradeResponse:
    """Create an editable draft after validating its profile references."""
    profile = await get_owned(
        session,
        TradingProfile,
        profile_id,
        user.id,
        for_update=True,
    )
    if profile.is_archived:
        conflict("Archived profiles cannot accept new trades")
    await validate_trade_identity(
        session,
        profile,
        request.strategy_id,
        request.instrument_id,
        user.id,
    )
    trade = Trade(
        profile_id=profile.id,
        strategy_id=request.strategy_id,
        instrument_id=request.instrument_id,
        trade_date=request.trade_date,
        status=TradeStatus.DRAFT,
        direction=request.direction,
        preparation=TradePreparation(),
        description_markdown=request.description_markdown,
    )
    session.add(trade)
    await session.flush()
    return await trade_response(session, trade)


@router.get(
    "/{trade_id}", response_model=TradeResponse, tags=["Profiles · Trades"]
)
async def get_trade(
    profile_id: int,
    trade_id: int,
    session: SessionDependency,
    user: CurrentUserDependency,
) -> TradeResponse:
    """Return the complete workspace for one owned trade."""
    trade = await get_profile_trade(session, trade_id, profile_id, user.id)
    return await trade_response(session, trade)


@router.delete(
    "/{trade_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=["Profiles · Trades"],
)
async def delete_trade(
    profile_id: int,
    trade_id: int,
    session: SessionDependency,
    user: CurrentUserDependency,
) -> None:
    """Permanently remove a draft that has never created immutable history."""
    trade = await get_profile_trade(
        session,
        trade_id,
        profile_id,
        user.id,
        for_update=True,
    )
    if trade.status != TradeStatus.DRAFT:
        conflict("Only a draft trade can be deleted")
    if (
        await session.scalar(
            select(Attachment.id)
            .where(Attachment.trade_id == trade.id)
            .limit(1)
        )
        is not None
    ):
        conflict("Delete trade attachments before deleting the draft")
    await session.delete(trade)
    await session.flush()


@router.patch(
    "/{trade_id}", response_model=TradeResponse, tags=["Profiles · Trades"]
)
async def update_trade(
    profile_id: int,
    trade_id: int,
    request: TradePatch,
    session: SessionDependency,
    user: CurrentUserDependency,
) -> TradeResponse:
    """Edit draft identity or universally editable journal metadata."""
    trade = await get_profile_trade(
        session,
        trade_id,
        profile_id,
        user.id,
        for_update=True,
    )
    values = request.model_dump(exclude_unset=True)
    draft_only = {
        "strategy_id",
        "instrument_id",
        "trade_date",
        "direction",
    }
    if trade.status != TradeStatus.DRAFT and draft_only & values.keys():
        conflict("Submitted trade identity is immutable")
    if draft_only & values.keys():
        profile = await get_owned(
            session,
            TradingProfile,
            trade.profile_id,
            user.id,
        )
        await validate_trade_identity(
            session,
            profile,
            values.get("strategy_id", trade.strategy_id),
            values.get("instrument_id", trade.instrument_id),
            user.id,
        )
    if any(
        field in values and values[field] != getattr(trade, field)
        for field in ("instrument_id", "trade_date")
    ):
        p = trade.preparation
        p.atr_value = p.atr_source = p.atr_contributing_date = (
            p.atr_observation_time
        ) = p.observed_session_range = None
        p.atr_stale = False
    for field, value in values.items():
        setattr(trade, field, value)
    await session.flush()
    return await trade_response(session, trade)


@router.put(
    "/{trade_id}/checklist",
    response_model=ChecklistResponse,
    tags=["Profiles · Trade preparation"],
)
async def update_checklist(
    profile_id: int,
    trade_id: int,
    request: ChecklistWrite,
    session: SessionDependency,
    user: CurrentUserDependency,
) -> ChecklistResponse:
    """Replace and assess the four directional answers on a draft trade."""
    trade = await get_profile_trade(
        session,
        trade_id,
        profile_id,
        user.id,
        for_update=True,
    )
    if trade.status != TradeStatus.DRAFT:
        conflict("Checklist is locked after trade submission")
    answers = request.model_dump()
    for field, value in answers.items():
        setattr(trade.preparation, field, value)
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


@router.post(
    "/{trade_id}/atr",
    response_model=ATRResponse,
    tags=["Profiles · Trade preparation"],
)
async def refresh_atr(
    profile_id: int,
    trade_id: int,
    market: MarketDependency,
    request: ATRRequest,
    session: SessionDependency,
    user: CurrentUserDependency,
) -> ATRResponse:
    """Refresh and save ATR context for a draft trade.

    Supply value for manual ATR; otherwise request automatic market data.
    Manual profiles require value (422, manual_atr_required). A manual
    contributing date cannot follow the trade date. Submission locks this
    context (409). Returned candles are transient and are not stored.
    """
    trade = await get_profile_trade(session, trade_id, profile_id, user.id)
    if trade.status != TradeStatus.DRAFT:
        conflict("ATR context is locked after trade submission")
    requested_instrument_id = trade.instrument_id
    requested_trade_date = trade.trade_date
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
        session_percent: Decimal | None = None
        if request.observed_session_range is not None:
            with localcontext() as decimal_context:
                decimal_context.prec = 96
                session_percent = stored_decimal(
                    request.observed_session_range
                    / request.value
                    * Decimal(100),
                )
        response = ATRResponse(
            value=request.value,
            source=ATRSource.MANUAL,
            contributing_date=request.contributing_date or trade.trade_date,
            observation_time=datetime.now(UTC),
            stale=request.stale,
            observed_session_range=request.observed_session_range,
            session_range_percent=session_percent,
        )
    else:
        instrument = await session.get(
            TradingInstrument,
            trade.instrument_id,
        )
        profile = await get_owned(
            session,
            TradingProfile,
            trade.profile_id,
            user.id,
        )
        if instrument is None:
            not_found("Trade market context")
        if profile.venue_type.value == "manual":
            api_error(
                422,
                "manual_atr_required",
                "Manual profiles require an ATR value",
            )
        if instrument.product.value not in ("spot", "perpetual_future"):
            api_error(
                422, "unsupported_product", "No automatic ATR for this product"
            )
        context = await market.atr(
            profile.venue_type.value,
            instrument.exec_symbol,
            instrument.product.value,
            trade.trade_date,
        )
        response = ATRResponse(
            value=stored_decimal(context.atr_value),
            source=ATRSource.AUTO,
            contributing_date=context.contributing_date,
            observation_time=datetime.now(UTC),
            stale=context.is_stale,
            observed_session_range=context.observed_session_range,
            session_range_percent=context.session_range_percent,
            candles=[
                CandleResponse(
                    date=candle.date,
                    open=candle.open,
                    high=candle.high,
                    low=candle.low,
                    close=candle.close,
                )
                for candle in context.candles
            ],
        )
    locked_trade = await session.scalar(
        owned_select(Trade, user.id)
        .where(Trade.id == trade_id, Trade.profile_id == profile_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if locked_trade is None:
        not_found("Trade")
    if locked_trade.status != TradeStatus.DRAFT:
        conflict("ATR context is locked after trade submission")
    if (
        locked_trade.instrument_id != requested_instrument_id
        or locked_trade.trade_date != requested_trade_date
    ):
        conflict("Trade context changed during ATR request")
    p = locked_trade.preparation
    p.atr_value = response.value
    p.atr_source = response.source
    p.atr_contributing_date = response.contributing_date
    p.atr_observation_time = response.observation_time.replace(tzinfo=None)
    p.atr_stale = response.stale
    p.observed_session_range = response.observed_session_range
    await session.flush()
    return response


@router.post(
    "/{trade_id}/plan/preview",
    response_model=TradePlanResponse,
    tags=["Profiles · Trade preparation"],
)
async def preview_trade_plan(
    profile_id: int,
    trade_id: int,
    request: TradePlanRequest,
    session: SessionDependency,
    user: CurrentUserDependency,
) -> TradePlanResponse:
    """Preview a draft position plan without saving it or reserving funds.

    The response includes capital checks, but preview does not enforce
    sufficient capital. Submission recalculates and enforces those checks
    against current state; a preview does not guarantee submission.
    """
    trade = await get_profile_trade(
        session,
        trade_id,
        profile_id,
        user.id,
        for_update=True,
    )
    context = await prepare_submission(
        session,
        trade,
        request.planned_entry,
        request.planned_stop,
        enforce_capital=False,
    )
    return plan_response(
        request.planned_entry,
        request.planned_stop,
        context,
    )


@router.get(
    "/{trade_id}/planning-context",
    response_model=TradePlanningContextResponse,
    tags=["Profiles · Trade preparation"],
)
async def get_trade_plan_context(
    profile_id: int,
    trade_id: int,
    session: SessionDependency,
    user: CurrentUserDependency,
) -> TradePlanningContextResponse:
    """Return stable exact inputs for a responsive local draft calculator."""
    trade = await get_profile_trade(session, trade_id, profile_id, user.id)
    context = await prepare_planning_context(
        session,
        trade,
        for_update=False,
    )
    inventory = await session.scalar(
        select(TradingAsset).where(
            TradingAsset.profile_id == trade.profile_id,
            TradingAsset.id == context.instrument.base_asset_id,
            TradingAsset.is_archived.is_(False),
        )
    )
    inventory_available = (
        await wallet_balance(session, inventory)
        - await wallet_reserved(session, inventory)
        if inventory is not None
        else Decimal(0)
    )
    return TradePlanningContextResponse(
        product=context.instrument.product.value,
        direction=trade.direction,
        base_asset_id=context.instrument.base_asset_id,
        settlement_asset_id=context.settlement_asset_id,
        inventory_asset_id=inventory.id if inventory else None,
        inventory_available=inventory_available,
        price_step=context.instrument.price_step,
        quantity_step=context.instrument.qty_step,
        minimum_quantity=context.instrument.min_qty,
        minimum_notional=context.instrument.min_notional,
        reward_multiple=int(context.strategy.reward_multiple),
        planned_risk_percent=context.strategy.risk_percent,
        target_risk_amount=context.target_risk_amount,
        allocation_capital=context.allocation.capital,
        already_reserved_risk=stored_decimal(context.already_reserved_risk),
        remaining_risk_capacity=stored_decimal(
            context.remaining_risk_capacity,
        ),
        risk_stop_capital=context.wallet_asset.risk_stop_capital,
        wallet_balance=stored_decimal(context.balance),
        wallet_reserved=stored_decimal(context.reserved_notional),
        wallet_available=stored_decimal(context.available),
        deposit_floor_breach=(
            context.wallet_asset.risk_stop_capital is not None
            and context.balance <= context.wallet_asset.risk_stop_capital
        ),
    )


@router.put(
    "/{trade_id}/plan",
    response_model=TradeResponse,
    tags=["Profiles · Trade preparation"],
)
async def save_trade_plan(
    profile_id: int,
    trade_id: int,
    request: TradePlanSave,
    session: SessionDependency,
    user: CurrentUserDependency,
) -> TradeResponse:
    """Replace the draft's saved entry and stop values.

    Omitted or null anchors are cleared. Supply both to retain a complete
    plan. This saves preparation only; it does not reserve funds or submit
    the trade. Submitted plans are locked (409).
    """
    trade = await get_profile_trade(
        session,
        trade_id,
        profile_id,
        user.id,
        for_update=True,
    )
    if trade.status != TradeStatus.DRAFT:
        conflict("Plan is locked after trade submission")
    trade.preparation.planned_entry = request.planned_entry
    trade.preparation.planned_stop = request.planned_stop
    if request.planned_entry is not None and request.planned_stop is not None:
        await prepare_submission(
            session,
            trade,
            request.planned_entry,
            request.planned_stop,
            enforce_capital=False,
        )
    await session.flush()
    return await trade_response(session, trade)


@router.post(
    "/{trade_id}/submit",
    response_model=TradeResponse,
    tags=["Profiles · Trade lifecycle"],
)
async def submit_draft(
    profile_id: int,
    trade_id: int,
    request: TradeSubmit,
    session: SessionDependency,
    user: CurrentUserDependency,
) -> TradeResponse:
    """Submit a draft as pending_entry or open.

    Save entry and stop first; missing anchors return 422 with
    missing_draft_plan. Submission recalculates the plan, checks capital,
    freezes one immutable snapshot and reserves the required asset amounts
    atomically. Invalid lifecycle or capital state returns 409.
    This records a journal decision; it does not place an exchange order.
    """
    trade = await get_profile_trade(
        session, trade_id, profile_id, user.id, for_update=True
    )
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


@router.post(
    "/{trade_id}/open",
    response_model=TradeResponse,
    tags=["Profiles · Trade lifecycle"],
)
async def open_trade(
    profile_id: int,
    trade_id: int,
    session: SessionDependency,
    user: CurrentUserDependency,
) -> TradeResponse:
    """Mark a pending external order as filled and open."""
    trade = await get_profile_trade(
        session,
        trade_id,
        profile_id,
        user.id,
        for_update=True,
    )
    if trade.status != TradeStatus.PENDING_ENTRY:
        conflict("Only a pending trade can be opened")
    trade.status = TradeStatus.OPEN
    trade.opened_at = datetime.now(UTC).replace(tzinfo=None)
    await session.flush()
    return await trade_response(session, trade)


@router.post(
    "/{trade_id}/cancel",
    response_model=TradeResponse,
    tags=["Profiles · Trade lifecycle"],
)
async def cancel_trade(
    profile_id: int,
    trade_id: int,
    session: SessionDependency,
    user: CurrentUserDependency,
) -> TradeResponse:
    """Cancel a draft, pending or open trade and release derived reservation."""
    trade = await get_profile_trade(
        session,
        trade_id,
        profile_id,
        user.id,
        for_update=True,
    )
    if trade.status not in (
        TradeStatus.DRAFT,
        TradeStatus.PENDING_ENTRY,
    ):
        conflict("Trade cannot be cancelled from its current state")
    trade.status = TradeStatus.CANCELLED
    trade.cancelled_at = datetime.now(UTC).replace(tzinfo=None)
    await session.flush()
    return await trade_response(session, trade)


@router.post(
    "/{trade_id}/close",
    response_model=TradeResponse,
    tags=["Profiles · Trade lifecycle"],
)
async def close_trade(
    profile_id: int,
    trade_id: int,
    request: TradeClose,
    session: SessionDependency,
    user: CurrentUserDependency,
) -> TradeResponse:
    """Close an open trade, release reservation and add realized P&L.

    Supply signed net P&L in the settlement asset, already including fees
    and funding. Commission and funding fields are recorded as context;
    they are not deducted again. Only open trades can close (409).
    """
    trade = await get_profile_trade(
        session,
        trade_id,
        profile_id,
        user.id,
        for_update=True,
    )
    if trade.status != TradeStatus.OPEN:
        conflict("Only an open trade can be closed")
    snapshot = await session.scalar(
        select(TradeSnapshot).where(TradeSnapshot.trade_id == trade.id)
    )
    if snapshot is None:
        conflict("An open trade requires an immutable snapshot")
    allocation = await session.get(
        StrategyCapital,
        snapshot.strategy_capital_id,
    )
    wallet_asset = (
        await session.get(TradingAsset, allocation.asset_id)
        if allocation is not None
        else None
    )
    if wallet_asset is None:
        conflict("The snapshotted allocation is no longer available")
    trade.status = TradeStatus.CLOSED
    trade.closed_at = datetime.now(UTC).replace(tzinfo=None)
    trade.realized_pnl = request.realized_pnl
    trade.actual_exit_price = request.actual_exit_price
    trade.total_commission = request.total_commission
    trade.funding_result = request.funding_result
    await session.flush()
    await recompute_wallet_asset(session, wallet_asset)
    await session.flush()
    return await trade_response(session, trade)


@router.put(
    "/{trade_id}/review",
    response_model=TradeResponse,
    tags=["Profiles · Trade lifecycle"],
)
async def review_trade(
    profile_id: int,
    trade_id: int,
    request: TradeReview,
    session: SessionDependency,
    user: CurrentUserDependency,
) -> TradeResponse:
    """Set review completion time on a closed trade."""
    trade = await get_profile_trade(
        session,
        trade_id,
        profile_id,
        user.id,
        for_update=True,
    )
    if trade.status != TradeStatus.CLOSED:
        conflict("Only a closed trade can be reviewed")
    trade.review_completed_at = (
        datetime.now(UTC).replace(tzinfo=None) if request.completed else None
    )
    await session.flush()
    return await trade_response(session, trade)

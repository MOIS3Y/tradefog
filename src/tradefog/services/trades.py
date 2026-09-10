"""Atomic trade validation, snapshot creation and derived context."""

from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import ROUND_HALF_EVEN, Decimal, InvalidOperation, localcontext

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from tradefog.api.errors import api_error, conflict, not_found
from tradefog.db.models import (
    StrategyCapital,
    Trade,
    TradeReservation,
    TradeSnapshot,
    TradingAsset,
    TradingInstrument,
    TradingProfile,
    TradingStrategy,
    Wallet,
    WalletAsset,
)
from tradefog.db.scoping import owned_select
from tradefog.domain.calculations import (
    PositionPlan,
    PositionPlanError,
    calculate_position_plan,
)
from tradefog.domain.checklists import (
    ChecklistAnswers,
    calculate_checklist_assessment,
)
from tradefog.domain.enums import (
    ATRSource,
    Direction,
    ProductKind,
    ReservationPurpose,
    TradeStatus,
)
from tradefog.services.journal import wallet_balance, wallet_reserved


@dataclass(frozen=True, slots=True)
class PlanningContext:
    """Stable strategy, instrument and capital inputs for position sizing."""

    strategy: TradingStrategy
    instrument: TradingInstrument
    allocation: StrategyCapital
    wallet_asset: WalletAsset
    settlement_asset_id: int
    balance: Decimal
    reserved_notional: Decimal
    available: Decimal
    target_risk_amount: Decimal
    already_reserved_risk: Decimal
    remaining_risk_capacity: Decimal
    atr: "ATRDecisionContext | None"


@dataclass(frozen=True, slots=True)
class SubmissionContext:
    """Validated executable plan and its decision-time capital context."""

    plan: PositionPlan
    strategy: TradingStrategy
    allocation: StrategyCapital
    wallet_asset: WalletAsset
    settlement_asset_id: int
    balance: Decimal
    reserved_notional: Decimal
    available: Decimal
    target_risk_amount: Decimal
    already_reserved_risk: Decimal
    remaining_risk_capacity: Decimal
    remaining_risk_after_plan: Decimal
    atr: "ATRDecisionContext | None"
    instrument: TradingInstrument
    reservations: list["ReservationRequirement"]


@dataclass(frozen=True, slots=True)
class ReservationRequirement:
    """An exact asset requirement and its current available balance."""

    wallet_asset_id: int
    asset_id: int
    purpose: ReservationPurpose
    amount: Decimal
    available: Decimal


@dataclass(frozen=True, slots=True)
class ATRDecisionContext:
    """Latest serializable ATR facts retained in a draft."""

    value: Decimal
    source: ATRSource
    contributing_date: date
    observation_time: datetime
    stale: bool
    observed_session_range: Decimal | None = None
    session_range_percent: Decimal | None = None


def checklist_payload(trade: Trade) -> dict[str, object]:
    """Assess typed preparation inputs without deserializing JSON."""
    preparation = trade.preparation
    values = {
        field: getattr(preparation, field)
        for field in (
            "market_sentiment",
            "information_background",
            "global_daily_direction",
            "local_daily_movement",
        )
    }
    answers = ChecklistAnswers(**values)
    assessment = calculate_checklist_assessment(
        answers, trade_direction=trade.direction.value
    )
    return {
        **values,
        "score": assessment.score,
        "direction": assessment.direction,
        "completeness": assessment.completeness,
        "answered_count": assessment.answered_count,
        "total_count": assessment.total_count,
        "gauge_position": assessment.gauge_position,
        "trend_relationship": assessment.trend_relationship,
        "agrees_with_trade": assessment.agrees_with_trade,
    }


def atr_from_context(trade: Trade) -> ATRDecisionContext | None:
    """Read typed ATR facts and calculate derived session percentage."""
    p = trade.preparation
    if (
        p.atr_value is None
        or p.atr_source is None
        or p.atr_contributing_date is None
        or p.atr_observation_time is None
    ):
        return None
    with localcontext() as context:
        context.prec = 96
        percent = (
            p.observed_session_range / p.atr_value * 100
            if p.observed_session_range is not None
            else None
        )
    return ATRDecisionContext(
        value=p.atr_value,
        source=p.atr_source,
        contributing_date=p.atr_contributing_date,
        observation_time=p.atr_observation_time,
        stale=p.atr_stale,
        observed_session_range=p.observed_session_range,
        session_range_percent=percent,
    )


async def validate_trade_identity(
    session: AsyncSession,
    profile: TradingProfile,
    strategy_id: int,
    instrument_id: int,
    owner_id: int,
) -> tuple[TradingStrategy, TradingInstrument]:
    """Validate profile ownership and same-profile/same-venue references."""
    strategy = await session.scalar(
        owned_select(TradingStrategy, owner_id).where(
            TradingStrategy.id == strategy_id,
            TradingStrategy.profile_id == profile.id,
        )
    )
    if strategy is None or strategy.is_archived:
        api_error(
            422, "invalid_strategy", "An active profile strategy is required"
        )
    instrument = await session.get(TradingInstrument, instrument_id)
    if (
        instrument is None
        or not instrument.is_active
        or instrument.profile_id != profile.id
        or instrument.is_archived
    ):
        api_error(
            422,
            "invalid_instrument",
            "An active instrument on the profile venue is required",
        )
    return strategy, instrument


async def settlement_allocation(
    session: AsyncSession,
    trade: Trade,
    *,
    active_only: bool = True,
    for_update: bool = True,
) -> tuple[StrategyCapital, WalletAsset]:
    """Resolve the active allocation matching the instrument settlement asset."""
    instrument = await session.get(TradingInstrument, trade.instrument_id)
    if instrument is None:
        not_found("TradingInstrument")
    settlement_id = instrument.settlement_asset_id
    wallet = await session.scalar(
        select(Wallet).where(Wallet.profile_id == trade.profile_id)
    )
    if wallet is None:
        conflict("Instrument has no resolvable settlement wallet asset")
    statement = (
        select(StrategyCapital, WalletAsset)
        .join(
            WalletAsset,
            WalletAsset.id == StrategyCapital.wallet_asset_id,
        )
        .where(
            StrategyCapital.strategy_id == trade.strategy_id,
            WalletAsset.wallet_id == wallet.id,
            WalletAsset.asset_id == settlement_id,
        )
    )
    if active_only:
        statement = statement.where(
            StrategyCapital.is_archived.is_(False),
            WalletAsset.is_archived.is_(False),
        )
    if for_update:
        statement = statement.with_for_update()
    row = (await session.execute(statement)).first()
    if row is None:
        conflict("Strategy requires an active allocation for settlement asset")
    return row[0], row[1]


def stored_decimal(
    value: Decimal,
    precision: int = 30,
    scale: int = 18,
) -> Decimal:
    """Normalize a derived value to a fixed-point database column."""
    with localcontext() as context:
        context.prec = 96
        try:
            normalized = value.quantize(
                Decimal(1).scaleb(-scale),
                rounding=ROUND_HALF_EVEN,
            )
        except InvalidOperation:
            api_error(
                422, "decimal_overflow", "Calculated value exceeds precision"
            )
    if abs(normalized) >= Decimal(10) ** (precision - scale):
        api_error(
            422, "decimal_overflow", "Calculated value exceeds precision"
        )
    return normalized


async def reserved_risk(
    session: AsyncSession,
    trade: Trade,
    allocation: StrategyCapital,
) -> Decimal:
    """Sum exact risk already committed by this allocation cohort."""
    values = (
        await session.scalars(
            select(TradeSnapshot.planned_risk_amount)
            .join(Trade, Trade.id == TradeSnapshot.trade_id)
            .where(
                TradeSnapshot.strategy_capital_id == allocation.id,
                Trade.id != trade.id,
                Trade.status.in_(
                    (TradeStatus.PENDING_ENTRY, TradeStatus.OPEN)
                ),
            )
        )
    ).all()
    return sum((value for value in values if value is not None), Decimal(0))


async def prepare_submission(
    session: AsyncSession,
    trade: Trade,
    entry: Decimal,
    stop: Decimal,
    *,
    enforce_capital: bool = True,
) -> SubmissionContext:
    """Validate a draft plan against current references and capital."""
    planning = await prepare_planning_context(session, trade)
    if (
        enforce_capital
        and planning.target_risk_amount > planning.remaining_risk_capacity
    ):
        conflict(
            "Strategy allocation has insufficient remaining risk capacity"
        )
    try:
        plan = calculate_position_plan(
            direction=trade.direction.value,
            entry=entry,
            stop=stop,
            target_risk_amount=planning.target_risk_amount,
            reward_multiple=planning.strategy.reward_multiple,
            price_step=planning.instrument.price_step,
            quantity_step=planning.instrument.qty_step,
            minimum_quantity=planning.instrument.min_qty,
            minimum_notional=planning.instrument.min_notional,
        )
    except PositionPlanError as error:
        api_error(422, "invalid_position_plan", error.message)
    reservations = await reservation_requirements(
        session, trade, planning, plan
    )
    if enforce_capital and any(
        row.amount > row.available for row in reservations
    ):
        api_error(
            409,
            "insufficient_reserves",
            "Insufficient available inventory or settlement funds",
        )
    return SubmissionContext(
        plan=plan,
        strategy=planning.strategy,
        allocation=planning.allocation,
        wallet_asset=planning.wallet_asset,
        settlement_asset_id=planning.settlement_asset_id,
        balance=planning.balance,
        reserved_notional=planning.reserved_notional,
        available=planning.available,
        target_risk_amount=planning.target_risk_amount,
        already_reserved_risk=planning.already_reserved_risk,
        remaining_risk_capacity=planning.remaining_risk_capacity,
        remaining_risk_after_plan=(
            planning.remaining_risk_capacity - plan.planned_risk_amount
        ),
        atr=planning.atr,
        instrument=planning.instrument,
        reservations=reservations,
    )


async def prepare_planning_context(
    session: AsyncSession,
    trade: Trade,
    *,
    for_update: bool = True,
) -> PlanningContext:
    """Resolve current inputs needed by both local and server calculations."""
    if trade.status != TradeStatus.DRAFT:
        conflict("Only a draft trade can be submitted")
    strategy = await session.get(TradingStrategy, trade.strategy_id)
    instrument = await session.get(TradingInstrument, trade.instrument_id)
    if strategy is None or instrument is None:
        conflict("Trade references are no longer available")
    profile = await session.get(TradingProfile, trade.profile_id)
    if (
        strategy.is_archived
        or not instrument.is_active
        or profile is None
        or profile.is_archived
        or strategy.profile_id != profile.id
        or instrument.profile_id != profile.id
        or instrument.is_archived
    ):
        conflict("Archived trade references cannot be submitted")
    allocation, wallet_asset = await settlement_allocation(
        session,
        trade,
        for_update=for_update,
    )
    for asset_id in {
        instrument.base_asset_id,
        instrument.quote_asset_id,
        instrument.settlement_asset_id,
    }:
        asset = await session.get(TradingAsset, asset_id)
        if (
            asset is None
            or not asset.is_active
            or asset.profile_id != trade.profile_id
        ):
            conflict("Instrument assets are unavailable in this profile")
    balance = await wallet_balance(session, wallet_asset)
    wallet_reserved_amount = await wallet_reserved(session, wallet_asset)
    available = balance - wallet_reserved_amount
    already_risk = await reserved_risk(session, trade, allocation)
    remaining_risk = allocation.capital - already_risk
    with localcontext() as context:
        context.prec = 96
        target_risk = stored_decimal(
            allocation.capital * strategy.risk_percent / Decimal(100),
        )
    return PlanningContext(
        strategy=strategy,
        instrument=instrument,
        allocation=allocation,
        wallet_asset=wallet_asset,
        settlement_asset_id=wallet_asset.asset_id,
        balance=balance,
        reserved_notional=wallet_reserved_amount,
        available=available,
        target_risk_amount=target_risk,
        already_reserved_risk=already_risk,
        remaining_risk_capacity=remaining_risk,
        atr=atr_from_context(trade),
    )


async def submit_trade(
    session: AsyncSession,
    trade: Trade,
    target_status: TradeStatus,
    entry: Decimal,
    stop: Decimal,
) -> TradeSnapshot:
    """Atomically freeze a validated draft plan and reserve its capital."""
    if target_status not in (TradeStatus.PENDING_ENTRY, TradeStatus.OPEN):
        conflict("A trade can only be submitted as pending or open")
    context = await prepare_submission(session, trade, entry, stop)
    atr = context.atr
    snapshot = TradeSnapshot(
        trade_id=trade.id,
        strategy_capital_id=context.allocation.id,
        settlement_asset_id=context.settlement_asset_id,
        instrument_symbol=context.instrument.exec_symbol,
        instrument_product=context.instrument.product,
        price_step=context.instrument.price_step,
        qty_step=context.instrument.qty_step,
        min_qty=context.instrument.min_qty,
        min_notional=context.instrument.min_notional,
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
        risk_stop_capital=context.wallet_asset.risk_stop_capital,
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
        atr_value=stored_decimal(atr.value) if atr else None,
        atr_source=atr.source if atr else None,
        atr_contributing_date=atr.contributing_date if atr else None,
        atr_observation_time=(
            atr.observation_time.replace(tzinfo=None) if atr else None
        ),
        atr_stale=atr.stale if atr else None,
    )
    session.add(snapshot)
    now = datetime.now(UTC).replace(tzinfo=None)
    trade.status = target_status
    trade.submitted_at = now
    if target_status == TradeStatus.OPEN:
        trade.opened_at = now
    await session.flush()
    session.add_all(
        [
            TradeReservation(
                trade_snapshot_id=snapshot.id,
                wallet_asset_id=row.wallet_asset_id,
                purpose=row.purpose,
                amount=stored_decimal(row.amount),
            )
            for row in context.reservations
        ]
    )
    await session.flush()
    return snapshot


async def reservation_requirements(
    session: AsyncSession,
    trade: Trade,
    planning: PlanningContext,
    plan: PositionPlan,
) -> list[ReservationRequirement]:
    """Require owned inventory plus a quote loss buffer for cash buybacks."""
    buyback = (
        trade.direction == Direction.SHORT
        and planning.instrument.product
        in (ProductKind.SPOT, ProductKind.CASH_EQUITY)
    )
    money = plan.planned_risk_amount if buyback else plan.notional
    rows = [
        ReservationRequirement(
            wallet_asset_id=planning.wallet_asset.id,
            asset_id=planning.wallet_asset.asset_id,
            purpose=ReservationPurpose.LOSS_BUFFER
            if buyback
            else ReservationPurpose.POSITION_FUNDING,
            amount=stored_decimal(money),
            available=planning.available,
        )
    ]
    if buyback:
        inventory = await session.scalar(
            select(WalletAsset)
            .join(Wallet)
            .where(
                Wallet.profile_id == trade.profile_id,
                WalletAsset.asset_id == planning.instrument.base_asset_id,
                WalletAsset.is_archived.is_(False),
            )
        )
        available = Decimal(0)
        if inventory is not None:
            available = await wallet_balance(
                session, inventory
            ) - await wallet_reserved(session, inventory)
        rows.append(
            ReservationRequirement(
                wallet_asset_id=inventory.id if inventory else 0,
                asset_id=planning.instrument.base_asset_id,
                purpose=ReservationPurpose.INVENTORY,
                amount=stored_decimal(plan.quantity),
                available=available,
            )
        )
    return rows

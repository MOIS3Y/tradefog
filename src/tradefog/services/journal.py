"""Owner-scoped journal lookup, balance and status services."""

from decimal import Decimal

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from tradefog.api.errors import conflict, not_found
from tradefog.db.models import (
    StrategyCapital,
    Trade,
    TradeSnapshot,
    TradingPair,
    TradingStrategy,
    VenueInstrument,
    VenueWalletAsset,
    Wallet,
    WalletAsset,
    WalletOperation,
)
from tradefog.db.scoping import JournalModel, owned_select
from tradefog.domain.capital import strategy_status, wallet_asset_status
from tradefog.domain.enums import TradeStatus, WalletOperationKind


async def get_owned[Model: JournalModel](
    session: AsyncSession,
    model: type[Model],
    identifier: int,
    owner_id: int,
    *,
    for_update: bool = False,
) -> Model:
    """Load one owner-scoped entity or expose no cross-owner information."""
    statement = owned_select(model, owner_id).where(model.id == identifier)
    if for_update:
        statement = statement.with_for_update()
    item = await session.scalar(statement)
    if item is None:
        not_found(model.__name__)
    return item


async def wallet_balance(
    session: AsyncSession,
    wallet_asset: WalletAsset,
) -> Decimal:
    """Derive exact balance from immutable operations and closed trade P&L."""
    operations = (
        await session.scalars(
            select(WalletOperation.amount).where(
                WalletOperation.wallet_asset_id == wallet_asset.id,
            )
        )
    ).all()
    capability = await session.get(
        VenueWalletAsset, wallet_asset.venue_wallet_asset_id,
    )
    if capability is None:
        return sum(operations, Decimal(0))
    profile_id = await session.scalar(
        select(Wallet.profile_id).where(Wallet.id == wallet_asset.wallet_id)
    )
    profits = (
        await session.scalars(
            select(Trade.realized_pnl)
            .join(
                VenueInstrument,
                VenueInstrument.id == Trade.venue_instrument_id,
            )
            .join(TradingPair, TradingPair.id == VenueInstrument.pair_id)
            .where(
                Trade.profile_id == profile_id,
                Trade.status == TradeStatus.CLOSED,
                Trade.realized_pnl.is_not(None),
                or_(
                    VenueInstrument.settlement_asset_id == capability.asset_id,
                    (
                        VenueInstrument.settlement_asset_id.is_(None)
                        & (TradingPair.quote_id == capability.asset_id)
                    ),
                ),
            )
        )
    ).all()
    return sum(operations, Decimal(0)) + sum(
        (value for value in profits if value is not None), Decimal(0),
    )


async def wallet_reserved(
    session: AsyncSession,
    wallet_asset: WalletAsset,
) -> Decimal:
    """Derive reserved notional for pending and open trades in this asset."""
    capability = await session.get(
        VenueWalletAsset, wallet_asset.venue_wallet_asset_id,
    )
    profile_id = await session.scalar(
        select(Wallet.profile_id).where(Wallet.id == wallet_asset.wallet_id)
    )
    if capability is None or profile_id is None:
        return Decimal(0)
    amounts = (
        await session.scalars(
            select(TradeSnapshot.planned_notional)
            .join(Trade, Trade.id == TradeSnapshot.trade_id)
            .join(
                VenueInstrument,
                VenueInstrument.id == Trade.venue_instrument_id,
            )
            .join(TradingPair, TradingPair.id == VenueInstrument.pair_id)
            .where(
                Trade.profile_id == profile_id,
                Trade.status.in_((TradeStatus.PENDING_ENTRY, TradeStatus.OPEN)),
                or_(
                    VenueInstrument.settlement_asset_id == capability.asset_id,
                    (
                        VenueInstrument.settlement_asset_id.is_(None)
                        & (TradingPair.quote_id == capability.asset_id)
                    ),
                ),
            )
        )
    ).all()
    return sum((value for value in amounts if value is not None), Decimal(0))


async def allocated_capital(
    session: AsyncSession,
    wallet_asset: WalletAsset,
) -> Decimal:
    """Sum capital committed by active strategies to a wallet asset."""
    values = (
        await session.scalars(
            select(StrategyCapital.capital).where(
                StrategyCapital.wallet_asset_id == wallet_asset.id,
                StrategyCapital.is_archived.is_(False),
            )
        )
    ).all()
    return sum(values, Decimal(0))


async def recompute_wallet_asset(
    session: AsyncSession,
    wallet_asset: WalletAsset,
) -> Decimal:
    """Persist derived wallet and dependent strategy statuses."""
    balance = await wallet_balance(session, wallet_asset)
    wallet_asset.status = wallet_asset_status(
        balance, wallet_asset.risk_stop_capital,
    )
    strategy_ids = (
        await session.scalars(
            select(StrategyCapital.strategy_id).where(
                StrategyCapital.wallet_asset_id == wallet_asset.id,
                StrategyCapital.is_archived.is_(False),
            )
        )
    ).all()
    for strategy_id in set(strategy_ids):
        await recompute_strategy(session, strategy_id)
    return balance


async def recompute_strategy(
    session: AsyncSession,
    strategy_id: int,
) -> None:
    """Persist the worst status among a strategy's active allocations."""
    strategy = await session.get(TradingStrategy, strategy_id)
    if strategy is None:
        return
    statuses = (
        await session.scalars(
            select(WalletAsset.status)
            .join(
                StrategyCapital,
                StrategyCapital.wallet_asset_id == WalletAsset.id,
            )
            .where(
                StrategyCapital.strategy_id == strategy_id,
                StrategyCapital.is_archived.is_(False),
                WalletAsset.is_archived.is_(False),
            )
        )
    ).all()
    strategy.status = strategy_status(list(statuses))


async def record_wallet_operation(
    session: AsyncSession,
    wallet_asset: WalletAsset,
    kind: WalletOperationKind,
    amount: Decimal,
    note: str | None,
) -> WalletOperation:
    """Append a signed ledger fact after checking available withdrawals."""
    balance = await wallet_balance(session, wallet_asset)
    reserved = await wallet_reserved(session, wallet_asset)
    allocated = await allocated_capital(session, wallet_asset)
    protected_capital = max(reserved, allocated)
    if (
        kind == WalletOperationKind.WITHDRAWAL
        and amount > balance - protected_capital
    ):
        conflict("Withdrawal exceeds uncommitted wallet balance")
    signed = amount if kind == WalletOperationKind.DEPOSIT else -amount
    operation = WalletOperation(
        wallet_asset_id=wallet_asset.id,
        kind=kind,
        amount=signed,
        note=note,
    )
    session.add(operation)
    await session.flush()
    await recompute_wallet_asset(session, wallet_asset)
    return operation

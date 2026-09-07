"""Fail-closed owner-scoped selects for every journal entity.

Callers must obtain owner_id from authentication, never from request data.
Shared catalog and user models are intentionally unsupported here.
"""

from sqlalchemy import Select, select
from sqlalchemy.sql.elements import ColumnElement

from tradefog.db.models import (
    StrategyCapital,
    Trade,
    TradeSnapshot,
    TradingProfile,
    TradingStrategy,
    Wallet,
    WalletAsset,
    WalletOperation,
)

type JournalModel = (
    TradingProfile
    | Wallet
    | WalletAsset
    | WalletOperation
    | TradingStrategy
    | StrategyCapital
    | Trade
    | TradeSnapshot
)


def owned_select[Model: JournalModel](
    model: type[Model],
    owner_id: int,
) -> Select[tuple[Model]]:
    """Select journal rows through the sole ownership root, the profile.

    Subqueries preserve one result per entity and leave the outer select
    free for additional filters, joins, counts and pagination. Unknown
    models raise rather than accidentally returning an unscoped query.
    """
    profiles = select(TradingProfile.id).where(
        TradingProfile.owner_id == owner_id,
    )
    wallets = select(Wallet.id).where(Wallet.profile_id.in_(profiles))
    assets = select(WalletAsset.id).where(WalletAsset.wallet_id.in_(wallets))
    strategies = select(TradingStrategy.id).where(
        TradingStrategy.profile_id.in_(profiles),
    )
    trades = select(Trade.id).where(Trade.profile_id.in_(profiles))
    predicates: dict[type[JournalModel], ColumnElement[bool]] = {
        TradingProfile: TradingProfile.owner_id == owner_id,
        Wallet: Wallet.profile_id.in_(profiles),
        WalletAsset: WalletAsset.wallet_id.in_(wallets),
        WalletOperation: WalletOperation.wallet_asset_id.in_(assets),
        TradingStrategy: TradingStrategy.profile_id.in_(profiles),
        StrategyCapital: StrategyCapital.strategy_id.in_(strategies),
        Trade: Trade.profile_id.in_(profiles),
        TradeSnapshot: TradeSnapshot.trade_id.in_(trades),
    }
    if model not in predicates:
        raise ValueError(f"Unsupported owner-scoped model: {model.__name__}")
    return select(model).where(predicates[model])

"""Journal and catalog model package.

Re-exports every model so Django discovers them during migration checks and
autodetection. The package is organized into cohesive modules:

- :mod:`catalog` — shared, staff-managed reference catalog;
- :mod:`profiles` — owner-scoped profile, wallet, and wallet operations;
- :mod:`strategies` — trading strategies;
- :mod:`trades` — trades and their write-once decision snapshots.
"""

from tradefog.journal.models.catalog import (
    Asset,
    TradingPair,
    Venue,
    VenueInstrument,
    VenueWalletAsset,
)
from tradefog.journal.models.profiles import (
    TradingProfile,
    Wallet,
    WalletAsset,
    WalletOperation,
)
from tradefog.journal.models.strategies import StrategyCapital, TradingStrategy
from tradefog.journal.models.trades import Trade, TradeSnapshot

__all__ = [
    "Asset",
    "StrategyCapital",
    "Trade",
    "TradeSnapshot",
    "TradingPair",
    "TradingProfile",
    "TradingStrategy",
    "Venue",
    "VenueInstrument",
    "VenueWalletAsset",
    "Wallet",
    "WalletAsset",
    "WalletOperation",
]

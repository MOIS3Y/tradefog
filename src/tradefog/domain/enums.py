"""Stored choices for journal, market, and catalog entities."""

from enum import StrEnum


class AssetType(StrEnum):
    """Unambiguous type of a shared asset."""

    CRYPTO = "crypto"
    EQUITY = "equity"
    FIAT = "fiat"


class ProductKind(StrEnum):
    """Executable market kind placed on a venue instrument."""

    SPOT = "spot"
    PERPETUAL_FUTURE = "perpetual_future"
    CASH_EQUITY = "cash_equity"


class ATRSource(StrEnum):
    """Origin of a frozen ATR snapshot value."""

    AUTO = "auto"
    MANUAL = "manual"


class VenueType(StrEnum):
    """Fixed integration choice, independent of user-owned profiles."""

    MANUAL = "manual"
    BYBIT = "bybit"


class ReservationPurpose(StrEnum):
    """Denomination-aware funding requirement frozen with a trade."""

    POSITION_FUNDING = "position_funding"
    INVENTORY = "inventory"
    LOSS_BUFFER = "loss_buffer"


class TradeStatus(StrEnum):
    """Lifecycle state of a journal trade."""

    DRAFT = "draft"
    PENDING_ENTRY = "pending_entry"
    OPEN = "open"
    CLOSED = "closed"
    CANCELLED = "cancelled"


class Direction(StrEnum):
    """Planned trade side."""

    LONG = "long"
    SHORT = "short"


class StrategyStatus(StrEnum):
    """Operational status recalculated from financial facts."""

    ACTIVE = "active"
    AT_RISK = "at_risk"
    RISK_STOPPED = "risk_stopped"


class WalletAssetStatus(StrEnum):
    """Money-health status of a wallet asset against its deposit floor."""

    ACTIVE = "active"
    AT_RISK = "at_risk"
    RISK_STOPPED = "risk_stopped"


class WalletOperationKind(StrEnum):
    """Kind of a virtual wallet journal operation."""

    DEPOSIT = "deposit"
    WITHDRAWAL = "withdrawal"

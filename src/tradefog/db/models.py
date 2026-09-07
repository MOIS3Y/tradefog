"""ORM entities matching the fourteen tables in docs/database.dbml."""

from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    String,
    Text,
    false,
    func,
    text,
    true,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from tradefog.db.base import Base as Base
from tradefog.db.base import PrimaryKeyMixin
from tradefog.db.types import ExactDecimal
from tradefog.domain.enums import (
    AssetType,
    ATRSource,
    Direction,
    MarketDataProvider,
    ProductKind,
    StrategyStatus,
    TradeStatus,
    WalletAssetStatus,
    WalletOperationKind,
)


def enum_values(members: type[StrEnum]) -> list[str]:
    """Return stable persisted enum values instead of Python member names."""
    return [member.value for member in members]


def enum_type(enum: type[StrEnum], name: str) -> Enum:
    """Persist enum values with portable database-level checks."""
    return Enum(
        enum,
        name=name,
        native_enum=False,
        create_constraint=True,
        validate_strings=True,
        values_callable=enum_values,
    )


class User(PrimaryKeyMixin, Base):
    """Persist users records from the source schema."""

    __tablename__: str = "users"
    username: Mapped[str] = mapped_column(
        String(150),
        unique=True,
    )
    password: Mapped[str] = mapped_column(
        String(128),
    )
    is_staff: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        server_default=false(),
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        server_default=true(),
    )


class Asset(PrimaryKeyMixin, Base):
    """Persist Asset records from the source schema."""

    __tablename__: str = "Asset"
    __table_args__: tuple[Index | CheckConstraint, ...] = (
        Index("asset_symbol_idx", "symbol", unique=True),
        CheckConstraint(
            "symbol = upper(trim(symbol))", name="normalized_symbol"
        ),
    )
    symbol: Mapped[str] = mapped_column(
        String(32),
    )
    name: Mapped[str | None] = mapped_column(
        String(255),
    )
    asset_type: Mapped[AssetType] = mapped_column(
        enum_type(AssetType, "asset_type"),
    )


class TradingPair(PrimaryKeyMixin, Base):
    """Persist TradingPair records from the source schema."""

    __tablename__: str = "TradingPair"
    __table_args__: tuple[Index | CheckConstraint, ...] = (
        Index(
            "trading_pair_base_quote_idx", "base_id", "quote_id", unique=True
        ),
    )
    base_id: Mapped[int] = mapped_column(
        ForeignKey("Asset.id"),
    )
    quote_id: Mapped[int] = mapped_column(
        ForeignKey("Asset.id"),
    )
    canonical_symbol: Mapped[str] = mapped_column(
        String(32),
        unique=True,
    )

    base: Mapped[Asset] = relationship(
        foreign_keys=[base_id],
        lazy="raise",
    )
    quote: Mapped[Asset] = relationship(
        foreign_keys=[quote_id],
        lazy="raise",
    )


class Venue(PrimaryKeyMixin, Base):
    """Persist Venue records from the source schema."""

    __tablename__: str = "Venue"
    __table_args__: tuple[Index | CheckConstraint, ...] = (
        Index("venue_name_idx", "name", unique=True),
    )
    name: Mapped[str] = mapped_column(
        String(128),
    )
    market_data_provider: Mapped[MarketDataProvider] = mapped_column(
        enum_type(MarketDataProvider, "market_data_provider"),
        default=MarketDataProvider.NONE,
        server_default="none",
    )
    description: Mapped[str | None] = mapped_column(
        Text,
    )
    website: Mapped[str | None] = mapped_column(
        String(255),
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        server_default=true(),
    )


class VenueInstrument(PrimaryKeyMixin, Base):
    """Persist VenueInstrument records from the source schema."""

    __tablename__: str = "VenueInstrument"
    __table_args__: tuple[Index | CheckConstraint, ...] = (
        Index(
            "venue_instrument_venue_pair_product_idx",
            "venue_id",
            "pair_id",
            "product",
            unique=True,
        ),
        Index(
            "venue_instrument_venue_exec_symbol_idx",
            "venue_id",
            "exec_symbol",
            unique=True,
        ),
    )
    venue_id: Mapped[int] = mapped_column(
        ForeignKey("Venue.id"),
    )
    pair_id: Mapped[int] = mapped_column(
        ForeignKey("TradingPair.id"),
    )
    product: Mapped[ProductKind] = mapped_column(
        enum_type(ProductKind, "product_kind"),
    )
    exec_symbol: Mapped[str] = mapped_column(
        String(64),
    )
    price_step: Mapped[Decimal] = mapped_column(
        ExactDecimal(30, 18),
    )
    qty_step: Mapped[Decimal] = mapped_column(
        ExactDecimal(30, 18),
    )
    min_qty: Mapped[Decimal | None] = mapped_column(
        ExactDecimal(30, 18),
    )
    min_notional: Mapped[Decimal | None] = mapped_column(
        ExactDecimal(30, 18),
    )
    settlement_asset_id: Mapped[int | None] = mapped_column(
        ForeignKey("Asset.id"),
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        server_default=true(),
    )

    venue: Mapped[Venue] = relationship(
        foreign_keys=[venue_id],
        lazy="raise",
    )
    pair: Mapped[TradingPair] = relationship(
        foreign_keys=[pair_id],
        lazy="raise",
    )
    settlement_asset: Mapped[Asset | None] = relationship(
        foreign_keys=[settlement_asset_id],
        lazy="raise",
    )


class VenueWalletAsset(PrimaryKeyMixin, Base):
    """Persist VenueWalletAsset records from the source schema."""

    __tablename__: str = "VenueWalletAsset"
    __table_args__: tuple[Index | CheckConstraint, ...] = (
        Index(
            "venue_wallet_asset_venue_asset_idx",
            "venue_id",
            "asset_id",
            unique=True,
        ),
    )
    venue_id: Mapped[int] = mapped_column(
        ForeignKey("Venue.id"),
    )
    asset_id: Mapped[int] = mapped_column(
        ForeignKey("Asset.id"),
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        server_default=true(),
    )

    venue: Mapped[Venue] = relationship(
        foreign_keys=[venue_id],
        lazy="raise",
    )
    asset: Mapped[Asset] = relationship(
        foreign_keys=[asset_id],
        lazy="raise",
    )


class TradingProfile(PrimaryKeyMixin, Base):
    """Persist TradingProfile records from the source schema."""

    __tablename__: str = "TradingProfile"
    owner_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"),
    )
    venue_id: Mapped[int] = mapped_column(
        ForeignKey("Venue.id"),
    )
    name: Mapped[str] = mapped_column(
        String(128),
    )
    description: Mapped[str | None] = mapped_column(
        Text,
    )
    is_archived: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        server_default=false(),
    )

    owner: Mapped[User] = relationship(
        foreign_keys=[owner_id],
        lazy="raise",
    )
    venue: Mapped[Venue] = relationship(
        foreign_keys=[venue_id],
        lazy="raise",
    )


class Wallet(PrimaryKeyMixin, Base):
    """Persist Wallet records from the source schema."""

    __tablename__: str = "Wallet"
    profile_id: Mapped[int] = mapped_column(
        ForeignKey("TradingProfile.id"),
        unique=True,
    )

    profile: Mapped[TradingProfile] = relationship(
        foreign_keys=[profile_id],
        lazy="raise",
    )


class WalletAsset(PrimaryKeyMixin, Base):
    """Persist WalletAsset records from the source schema."""

    __tablename__: str = "WalletAsset"
    __table_args__: tuple[Index | CheckConstraint, ...] = (
        Index(
            "wallet_asset_wallet_venue_asset_idx",
            "wallet_id",
            "venue_wallet_asset_id",
            unique=True,
        ),
    )
    wallet_id: Mapped[int] = mapped_column(
        ForeignKey("Wallet.id"),
    )
    venue_wallet_asset_id: Mapped[int] = mapped_column(
        ForeignKey("VenueWalletAsset.id"),
    )
    risk_stop_capital: Mapped[Decimal | None] = mapped_column(
        ExactDecimal(30, 18),
    )
    status: Mapped[WalletAssetStatus] = mapped_column(
        enum_type(WalletAssetStatus, "wallet_asset_status"),
    )
    is_archived: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        server_default=false(),
    )

    wallet: Mapped[Wallet] = relationship(
        foreign_keys=[wallet_id],
        lazy="raise",
    )
    venue_wallet_asset: Mapped[VenueWalletAsset] = relationship(
        foreign_keys=[venue_wallet_asset_id],
        lazy="raise",
    )


class WalletOperation(PrimaryKeyMixin, Base):
    """Persist WalletOperation records from the source schema."""

    __tablename__: str = "WalletOperation"
    wallet_asset_id: Mapped[int] = mapped_column(
        ForeignKey("WalletAsset.id"),
    )
    kind: Mapped[WalletOperationKind] = mapped_column(
        enum_type(WalletOperationKind, "wallet_operation_kind"),
    )
    amount: Mapped[Decimal] = mapped_column(
        ExactDecimal(30, 18),
    )
    note: Mapped[str | None] = mapped_column(
        String(255),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
    )

    wallet_asset: Mapped[WalletAsset] = relationship(
        foreign_keys=[wallet_asset_id],
        lazy="raise",
    )


class TradingStrategy(PrimaryKeyMixin, Base):
    """Persist TradingStrategy records from the source schema."""

    __tablename__: str = "TradingStrategy"
    profile_id: Mapped[int] = mapped_column(
        ForeignKey("TradingProfile.id"),
    )
    name: Mapped[str] = mapped_column(
        String(128),
    )
    description: Mapped[str | None] = mapped_column(
        Text,
    )
    risk_percent: Mapped[Decimal] = mapped_column(
        ExactDecimal(10, 6),
    )
    reward_multiple: Mapped[Decimal] = mapped_column(
        ExactDecimal(10, 6),
        default=Decimal(3),
        server_default="3.000000",
    )
    status: Mapped[StrategyStatus] = mapped_column(
        enum_type(StrategyStatus, "strategy_status"),
    )
    is_archived: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        server_default=false(),
    )

    profile: Mapped[TradingProfile] = relationship(
        foreign_keys=[profile_id],
        lazy="raise",
    )


class StrategyCapital(PrimaryKeyMixin, Base):
    """Persist StrategyCapital records from the source schema."""

    __tablename__: str = "StrategyCapital"
    __table_args__: tuple[Index | CheckConstraint, ...] = (
        Index(
            "strategy_capital_strategy_wallet_asset_idx",
            "strategy_id",
            "wallet_asset_id",
            unique=True,
        ),
    )
    strategy_id: Mapped[int] = mapped_column(
        ForeignKey("TradingStrategy.id"),
    )
    wallet_asset_id: Mapped[int] = mapped_column(
        ForeignKey("WalletAsset.id"),
    )
    capital: Mapped[Decimal] = mapped_column(
        ExactDecimal(30, 18),
    )
    is_archived: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        server_default=false(),
    )

    strategy: Mapped[TradingStrategy] = relationship(
        foreign_keys=[strategy_id],
        lazy="raise",
    )
    wallet_asset: Mapped[WalletAsset] = relationship(
        foreign_keys=[wallet_asset_id],
        lazy="raise",
    )


class Trade(PrimaryKeyMixin, Base):
    """Persist Trade records from the source schema."""

    __tablename__: str = "Trade"
    profile_id: Mapped[int] = mapped_column(
        ForeignKey("TradingProfile.id"),
    )
    strategy_id: Mapped[int] = mapped_column(
        ForeignKey("TradingStrategy.id"),
    )
    venue_instrument_id: Mapped[int] = mapped_column(
        ForeignKey("VenueInstrument.id"),
    )
    trade_date: Mapped[date] = mapped_column(
        Date,
    )
    status: Mapped[TradeStatus] = mapped_column(
        enum_type(TradeStatus, "trade_status"),
    )
    direction: Mapped[Direction] = mapped_column(
        enum_type(Direction, "direction"),
    )
    draft_context: Mapped[dict[str, Any]] = mapped_column(
        JSON,
        default=dict,
        server_default=text("'{}'"),
    )
    description_markdown: Mapped[str | None] = mapped_column(
        Text,
    )
    review_completed_at: Mapped[datetime | None] = mapped_column(
        DateTime,
    )
    realized_pnl: Mapped[Decimal | None] = mapped_column(
        ExactDecimal(30, 18),
    )
    actual_exit_price: Mapped[Decimal | None] = mapped_column(
        ExactDecimal(30, 18),
    )
    total_commission: Mapped[Decimal | None] = mapped_column(
        ExactDecimal(30, 18),
    )
    funding_result: Mapped[Decimal | None] = mapped_column(
        ExactDecimal(30, 18),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
    )

    profile: Mapped[TradingProfile] = relationship(
        foreign_keys=[profile_id],
        lazy="raise",
    )
    strategy: Mapped[TradingStrategy] = relationship(
        foreign_keys=[strategy_id],
        lazy="raise",
    )
    venue_instrument: Mapped[VenueInstrument] = relationship(
        foreign_keys=[venue_instrument_id],
        lazy="raise",
    )


class TradeSnapshot(PrimaryKeyMixin, Base):
    """Persist TradeSnapshot records from the source schema."""

    __tablename__: str = "TradeSnapshot"
    trade_id: Mapped[int] = mapped_column(
        ForeignKey("Trade.id"),
        unique=True,
    )
    planned_entry: Mapped[Decimal] = mapped_column(
        ExactDecimal(30, 18),
    )
    planned_stop: Mapped[Decimal] = mapped_column(
        ExactDecimal(30, 18),
    )
    planned_take_profit: Mapped[Decimal | None] = mapped_column(
        ExactDecimal(30, 18),
    )
    quantity: Mapped[Decimal | None] = mapped_column(
        ExactDecimal(30, 18),
    )
    reward_multiple: Mapped[Decimal | None] = mapped_column(
        ExactDecimal(10, 6),
    )
    planned_risk_percent: Mapped[Decimal | None] = mapped_column(
        ExactDecimal(10, 6),
    )
    planned_risk_amount: Mapped[Decimal | None] = mapped_column(
        ExactDecimal(30, 18),
    )
    planned_notional: Mapped[Decimal | None] = mapped_column(
        ExactDecimal(30, 18),
    )
    allocation_capital: Mapped[Decimal | None] = mapped_column(
        ExactDecimal(30, 18),
    )
    risk_stop_capital: Mapped[Decimal | None] = mapped_column(
        ExactDecimal(30, 18),
    )
    already_reserved_risk: Mapped[Decimal | None] = mapped_column(
        ExactDecimal(30, 18),
    )
    remaining_risk_capacity: Mapped[Decimal | None] = mapped_column(
        ExactDecimal(30, 18),
    )
    deposit_floor_breach: Mapped[bool | None] = mapped_column(
        Boolean,
    )
    wallet_balance: Mapped[Decimal | None] = mapped_column(
        ExactDecimal(30, 18),
    )
    wallet_reserved: Mapped[Decimal | None] = mapped_column(
        ExactDecimal(30, 18),
    )
    wallet_available: Mapped[Decimal | None] = mapped_column(
        ExactDecimal(30, 18),
    )
    atr_value: Mapped[Decimal | None] = mapped_column(
        ExactDecimal(30, 18),
    )
    atr_source: Mapped[ATRSource | None] = mapped_column(
        enum_type(ATRSource, "atr_source"),
    )
    atr_contributing_date: Mapped[date | None] = mapped_column(
        Date,
    )
    atr_observation_time: Mapped[datetime | None] = mapped_column(
        DateTime,
    )
    atr_stale: Mapped[bool | None] = mapped_column(
        Boolean,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
    )

    trade: Mapped[Trade] = relationship(
        foreign_keys=[trade_id],
        lazy="raise",
    )

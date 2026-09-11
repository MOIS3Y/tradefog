"""ORM entities matching the tables in docs/database.dbml."""

from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum

from sqlalchemy import (
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
    true,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from tradefog.db.base import Base, PrimaryKeyMixin
from tradefog.db.types import ExactDecimal
from tradefog.domain.checklists import DirectionalValue
from tradefog.domain.enums import (
    AssetType,
    ATRSource,
    Direction,
    ProductKind,
    ReservationPurpose,
    StrategyStatus,
    TradeStatus,
    VenueType,
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
    first_name: Mapped[str | None] = mapped_column(String(150))
    last_name: Mapped[str | None] = mapped_column(String(150))
    email: Mapped[str | None] = mapped_column(String(254))
    preferred_locale: Mapped[str | None] = mapped_column(String(2))
    auth_version: Mapped[int] = mapped_column(default=0, server_default="0")
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )
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


class TradingAsset(PrimaryKeyMixin, Base):
    """Persist TradingAsset records from the source schema."""

    __tablename__: str = "TradingAsset"
    profile_id: Mapped[int] = mapped_column(ForeignKey("TradingProfile.id"))
    is_archived: Mapped[bool] = mapped_column(
        default=False, server_default=false()
    )
    risk_stop_capital: Mapped[Decimal | None] = mapped_column(
        ExactDecimal(30, 18)
    )
    status: Mapped[WalletAssetStatus] = mapped_column(
        enum_type(WalletAssetStatus, "wallet_asset_status"),
        default=WalletAssetStatus.ACTIVE,
        server_default="active",
    )
    __table_args__: tuple[Index | CheckConstraint, ...] = (
        Index("profile_asset_symbol_idx", "profile_id", "symbol", unique=True),
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


class TradingInstrument(PrimaryKeyMixin, Base):
    """Profile-owned executable instrument, imported or entered manually."""

    __tablename__ = "TradingInstrument"
    __table_args__ = (
        Index(
            "profile_instrument_symbol_idx",
            "profile_id",
            "product",
            "exec_symbol",
            unique=True,
        ),
        CheckConstraint(
            "base_asset_id != quote_asset_id",
            name="distinct_instrument_assets",
        ),
        CheckConstraint(
            "CAST(price_step AS NUMERIC) > 0", name="positive_price_step"
        ),
        CheckConstraint(
            "CAST(qty_step AS NUMERIC) > 0", name="positive_qty_step"
        ),
    )
    profile_id: Mapped[int] = mapped_column(ForeignKey("TradingProfile.id"))
    base_asset_id: Mapped[int] = mapped_column(ForeignKey("TradingAsset.id"))
    quote_asset_id: Mapped[int] = mapped_column(ForeignKey("TradingAsset.id"))
    settlement_asset_id: Mapped[int] = mapped_column(
        ForeignKey("TradingAsset.id")
    )
    product: Mapped[ProductKind] = mapped_column(
        enum_type(ProductKind, "product_kind")
    )
    exec_symbol: Mapped[str] = mapped_column(String(65))
    price_step: Mapped[Decimal] = mapped_column(ExactDecimal(30, 18))
    qty_step: Mapped[Decimal] = mapped_column(ExactDecimal(30, 18))
    min_qty: Mapped[Decimal | None] = mapped_column(ExactDecimal(30, 18))
    min_notional: Mapped[Decimal | None] = mapped_column(ExactDecimal(30, 18))
    metadata_updated_at: Mapped[datetime | None] = mapped_column(DateTime)
    is_active: Mapped[bool] = mapped_column(
        default=True, server_default=true()
    )
    is_archived: Mapped[bool] = mapped_column(
        default=False, server_default=false()
    )
    base_asset: Mapped[TradingAsset] = relationship(
        foreign_keys=[base_asset_id], lazy="raise"
    )
    quote_asset: Mapped[TradingAsset] = relationship(
        foreign_keys=[quote_asset_id], lazy="raise"
    )
    settlement_asset: Mapped[TradingAsset] = relationship(
        foreign_keys=[settlement_asset_id], lazy="raise"
    )


class TradingProfile(PrimaryKeyMixin, Base):
    """Persist TradingProfile records from the source schema."""

    __tablename__: str = "TradingProfile"
    __table_args__ = (Index("profile_owner_idx", "owner_id", "id"),)
    owner_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"),
    )
    venue_url: Mapped[str | None] = mapped_column(String(2048))
    venue_type: Mapped[VenueType] = mapped_column(
        enum_type(VenueType, "venue_type")
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


class WalletOperation(PrimaryKeyMixin, Base):
    """Persist WalletOperation records from the source schema."""

    __tablename__: str = "WalletOperation"
    asset_id: Mapped[int] = mapped_column(
        ForeignKey("TradingAsset.id"),
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

    wallet_asset: Mapped[TradingAsset] = relationship(
        foreign_keys=[asset_id],
        lazy="raise",
    )


class TradingStrategy(PrimaryKeyMixin, Base):
    """Persist TradingStrategy records from the source schema."""

    __tablename__: str = "TradingStrategy"
    __table_args__: tuple[CheckConstraint, ...] = (
        CheckConstraint(
            """CAST(risk_percent AS NUMERIC) >= 0.01
            AND CAST(risk_percent AS NUMERIC) <= 100""",
            name="strategy_risk_percent_range",
        ),
        CheckConstraint(
            """CAST(reward_multiple AS NUMERIC) >= 3
            AND CAST(reward_multiple AS NUMERIC) <= 100
            AND CAST(reward_multiple AS NUMERIC)
                = CAST(reward_multiple AS INTEGER)""",
            name="strategy_reward_multiple_range",
        ),
    )
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
            "asset_id",
            unique=True,
        ),
    )
    strategy_id: Mapped[int] = mapped_column(
        ForeignKey("TradingStrategy.id"),
    )
    asset_id: Mapped[int] = mapped_column(
        ForeignKey("TradingAsset.id"),
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
    wallet_asset: Mapped[TradingAsset] = relationship(
        foreign_keys=[asset_id],
        lazy="raise",
    )


class Trade(PrimaryKeyMixin, Base):
    """Persist Trade records from the source schema."""

    __tablename__: str = "Trade"
    __table_args__: tuple[Index | CheckConstraint, ...] = (
        Index("trade_profile_date_idx", "profile_id", "trade_date", "id"),
        Index(
            "trade_profile_rating_idx", "profile_id", "quality_rating", "id"
        ),
        Index(
            "trade_profile_review_idx",
            "profile_id",
            "status",
            "review_completed_at",
            "id",
        ),
        CheckConstraint(
            """quality_rating IS NULL
            OR (quality_rating >= 1 AND quality_rating <= 10)""",
            name="trade_quality_rating_range",
        ),
    )
    profile_id: Mapped[int] = mapped_column(
        ForeignKey("TradingProfile.id"),
    )
    strategy_id: Mapped[int] = mapped_column(
        ForeignKey("TradingStrategy.id"),
    )
    instrument_id: Mapped[int] = mapped_column(
        ForeignKey("TradingInstrument.id"),
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
    preparation: Mapped["TradePreparation"] = relationship(
        lazy="selectin",
        cascade="all, delete-orphan",
        single_parent=True,
    )
    description_markdown: Mapped[str | None] = mapped_column(
        Text,
    )
    quality_rating: Mapped[int | None] = mapped_column()
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
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime)
    opened_at: Mapped[datetime | None] = mapped_column(DateTime)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime)
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
    instrument: Mapped[TradingInstrument] = relationship(
        foreign_keys=[instrument_id],
        lazy="raise",
    )


class TradeSnapshot(PrimaryKeyMixin, Base):
    """Persist TradeSnapshot records from the source schema."""

    __tablename__: str = "TradeSnapshot"
    trade_id: Mapped[int] = mapped_column(
        ForeignKey("Trade.id"),
        unique=True,
    )
    strategy_capital_id: Mapped[int] = mapped_column(
        ForeignKey("StrategyCapital.id"),
    )
    settlement_asset_id: Mapped[int] = mapped_column(
        ForeignKey("TradingAsset.id"),
    )
    instrument_symbol: Mapped[str] = mapped_column(String(64))
    instrument_product: Mapped[ProductKind] = mapped_column(
        enum_type(ProductKind, "snapshot_product_kind")
    )
    price_step: Mapped[Decimal] = mapped_column(ExactDecimal(30, 18))
    qty_step: Mapped[Decimal] = mapped_column(ExactDecimal(30, 18))
    min_qty: Mapped[Decimal | None] = mapped_column(ExactDecimal(30, 18))
    min_notional: Mapped[Decimal | None] = mapped_column(ExactDecimal(30, 18))
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
    strategy_capital: Mapped[StrategyCapital] = relationship(
        foreign_keys=[strategy_capital_id],
        lazy="raise",
    )
    settlement_asset: Mapped[TradingAsset] = relationship(
        foreign_keys=[settlement_asset_id],
        lazy="raise",
    )


class Attachment(PrimaryKeyMixin, Base):
    """Persist private file metadata for one owner-scoped trade."""

    __tablename__: str = "Attachment"
    __table_args__: tuple[CheckConstraint, ...] = (
        CheckConstraint("size_bytes >= 0", name="non_negative_size"),
    )
    trade_id: Mapped[int] = mapped_column(
        ForeignKey("Trade.id"),
    )
    storage_key: Mapped[str] = mapped_column(
        String(255),
        unique=True,
    )
    original_name: Mapped[str] = mapped_column(
        String(255),
    )
    content_type: Mapped[str] = mapped_column(
        String(127),
    )
    size_bytes: Mapped[int] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
    )

    trade: Mapped[Trade] = relationship(
        foreign_keys=[trade_id],
        lazy="raise",
    )


class TradePreparation(Base):
    """Typed nullable draft inputs retained and locked after submission."""

    __tablename__ = "TradePreparation"
    trade_id: Mapped[int] = mapped_column(
        ForeignKey("Trade.id"), primary_key=True
    )
    planned_entry: Mapped[Decimal | None] = mapped_column(ExactDecimal(30, 18))
    planned_stop: Mapped[Decimal | None] = mapped_column(ExactDecimal(30, 18))
    market_sentiment: Mapped[DirectionalValue | None] = mapped_column(
        enum_type(DirectionalValue, "market_sentiment")
    )
    information_background: Mapped[DirectionalValue | None] = mapped_column(
        enum_type(DirectionalValue, "information_background")
    )
    global_daily_direction: Mapped[DirectionalValue | None] = mapped_column(
        enum_type(DirectionalValue, "global_daily_direction")
    )
    local_daily_movement: Mapped[DirectionalValue | None] = mapped_column(
        enum_type(DirectionalValue, "local_daily_movement")
    )
    atr_value: Mapped[Decimal | None] = mapped_column(ExactDecimal(30, 18))
    atr_source: Mapped[ATRSource | None] = mapped_column(
        enum_type(ATRSource, "preparation_atr_source")
    )
    atr_contributing_date: Mapped[date | None] = mapped_column(Date)
    atr_observation_time: Mapped[datetime | None] = mapped_column(DateTime)
    atr_stale: Mapped[bool] = mapped_column(
        default=False, server_default=false()
    )
    observed_session_range: Mapped[Decimal | None] = mapped_column(
        ExactDecimal(30, 18)
    )
    __table_args__ = (
        CheckConstraint(
            "planned_entry IS NULL OR CAST(planned_entry AS NUMERIC) > 0",
            name="positive_preparation_entry",
        ),
        CheckConstraint(
            "planned_stop IS NULL OR CAST(planned_stop AS NUMERIC) > 0",
            name="positive_preparation_stop",
        ),
        CheckConstraint(
            "observed_session_range IS NULL OR CAST(observed_session_range AS NUMERIC) >= 0",
            name="nonnegative_session_range",
        ),
        CheckConstraint(
            "(atr_value IS NULL AND atr_source IS NULL AND atr_contributing_date IS NULL AND atr_observation_time IS NULL AND observed_session_range IS NULL) OR "
            + "(atr_value IS NOT NULL AND CAST(atr_value AS NUMERIC) > 0 AND atr_source IS NOT NULL AND atr_contributing_date IS NOT NULL AND atr_observation_time IS NOT NULL)",
            name="complete_preparation_atr",
        ),
    )


class TradeReservation(PrimaryKeyMixin, Base):
    """Immutable requirements active only while the trade is pending/open."""

    __tablename__ = "TradeReservation"
    trade_snapshot_id: Mapped[int] = mapped_column(
        ForeignKey("TradeSnapshot.id")
    )
    asset_id: Mapped[int] = mapped_column(ForeignKey("TradingAsset.id"))
    purpose: Mapped[ReservationPurpose] = mapped_column(
        enum_type(ReservationPurpose, "reservation_purpose")
    )
    amount: Mapped[Decimal] = mapped_column(ExactDecimal(30, 18))
    __table_args__ = (
        Index(
            "reservation_snapshot_purpose_idx",
            "trade_snapshot_id",
            "purpose",
            unique=True,
        ),
        Index(
            "reservation_wallet_snapshot_idx",
            "asset_id",
            "trade_snapshot_id",
        ),
        CheckConstraint(
            "CAST(amount AS NUMERIC) > 0", name="positive_reservation"
        ),
    )

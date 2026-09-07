"""Initial journal and catalog schema.

Revision ID: 0001
Revises: None
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

import tradefog.db.types

revision: str = "0001"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Apply this schema revision."""
    _ = op.create_table(
        "Asset",
        sa.Column("symbol", sa.String(length=32), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=True),
        sa.Column(
            "asset_type",
            sa.Enum(
                "crypto",
                "equity",
                "fiat",
                name="asset_type",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.CheckConstraint(
            "symbol = upper(trim(symbol))",
            name=op.f("ck_Asset_normalized_symbol"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_Asset")),
    )
    with op.batch_alter_table("Asset", schema=None) as batch_op:
        batch_op.create_index("asset_symbol_idx", ["symbol"], unique=True)

    _ = op.create_table(
        "Venue",
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column(
            "market_data_provider",
            sa.Enum(
                "none",
                "bybit",
                "binance",
                "yfinance",
                name="market_data_provider",
                native_enum=False,
                create_constraint=True,
            ),
            server_default="none",
            nullable=False,
        ),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("website", sa.String(length=255), nullable=True),
        sa.Column(
            "is_active", sa.Boolean(), server_default=sa.true(), nullable=False
        ),
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_Venue")),
    )
    with op.batch_alter_table("Venue", schema=None) as batch_op:
        batch_op.create_index("venue_name_idx", ["name"], unique=True)

    _ = op.create_table(
        "users",
        sa.Column("username", sa.String(length=150), nullable=False),
        sa.Column("password", sa.String(length=128), nullable=False),
        sa.Column(
            "is_staff", sa.Boolean(), server_default=sa.false(), nullable=False
        ),
        sa.Column(
            "is_active", sa.Boolean(), server_default=sa.true(), nullable=False
        ),
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_users")),
        sa.UniqueConstraint("username", name=op.f("uq_users_username")),
    )
    _ = op.create_table(
        "TradingPair",
        sa.Column("base_id", sa.Integer(), nullable=False),
        sa.Column("quote_id", sa.Integer(), nullable=False),
        sa.Column("canonical_symbol", sa.String(length=32), nullable=False),
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.ForeignKeyConstraint(
            ["base_id"],
            ["Asset.id"],
            name=op.f("fk_TradingPair_base_id_Asset"),
        ),
        sa.ForeignKeyConstraint(
            ["quote_id"],
            ["Asset.id"],
            name=op.f("fk_TradingPair_quote_id_Asset"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_TradingPair")),
        sa.UniqueConstraint(
            "canonical_symbol", name=op.f("uq_TradingPair_canonical_symbol")
        ),
    )
    with op.batch_alter_table("TradingPair", schema=None) as batch_op:
        batch_op.create_index(
            "trading_pair_base_quote_idx", ["base_id", "quote_id"], unique=True
        )

    _ = op.create_table(
        "TradingProfile",
        sa.Column("owner_id", sa.Integer(), nullable=False),
        sa.Column("venue_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "is_archived",
            sa.Boolean(),
            server_default=sa.false(),
            nullable=False,
        ),
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.ForeignKeyConstraint(
            ["owner_id"],
            ["users.id"],
            name=op.f("fk_TradingProfile_owner_id_users"),
        ),
        sa.ForeignKeyConstraint(
            ["venue_id"],
            ["Venue.id"],
            name=op.f("fk_TradingProfile_venue_id_Venue"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_TradingProfile")),
    )
    _ = op.create_table(
        "VenueWalletAsset",
        sa.Column("venue_id", sa.Integer(), nullable=False),
        sa.Column("asset_id", sa.Integer(), nullable=False),
        sa.Column(
            "is_active", sa.Boolean(), server_default=sa.true(), nullable=False
        ),
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.ForeignKeyConstraint(
            ["asset_id"],
            ["Asset.id"],
            name=op.f("fk_VenueWalletAsset_asset_id_Asset"),
        ),
        sa.ForeignKeyConstraint(
            ["venue_id"],
            ["Venue.id"],
            name=op.f("fk_VenueWalletAsset_venue_id_Venue"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_VenueWalletAsset")),
    )
    with op.batch_alter_table("VenueWalletAsset", schema=None) as batch_op:
        batch_op.create_index(
            "venue_wallet_asset_venue_asset_idx",
            ["venue_id", "asset_id"],
            unique=True,
        )

    _ = op.create_table(
        "TradingStrategy",
        sa.Column("profile_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "risk_percent",
            tradefog.db.types.ExactDecimal(precision=10, scale=6),
            nullable=False,
        ),
        sa.Column(
            "reward_multiple",
            tradefog.db.types.ExactDecimal(precision=10, scale=6),
            server_default="3.000000",
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.Enum(
                "active",
                "at_risk",
                "risk_stopped",
                name="strategy_status",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column(
            "is_archived",
            sa.Boolean(),
            server_default=sa.false(),
            nullable=False,
        ),
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.ForeignKeyConstraint(
            ["profile_id"],
            ["TradingProfile.id"],
            name=op.f("fk_TradingStrategy_profile_id_TradingProfile"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_TradingStrategy")),
    )
    _ = op.create_table(
        "VenueInstrument",
        sa.Column("venue_id", sa.Integer(), nullable=False),
        sa.Column("pair_id", sa.Integer(), nullable=False),
        sa.Column(
            "product",
            sa.Enum(
                "spot",
                "perpetual_future",
                "cash_equity",
                name="product_kind",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column("exec_symbol", sa.String(length=64), nullable=False),
        sa.Column(
            "price_step",
            tradefog.db.types.ExactDecimal(precision=30, scale=18),
            nullable=False,
        ),
        sa.Column(
            "qty_step",
            tradefog.db.types.ExactDecimal(precision=30, scale=18),
            nullable=False,
        ),
        sa.Column(
            "min_qty",
            tradefog.db.types.ExactDecimal(precision=30, scale=18),
            nullable=True,
        ),
        sa.Column(
            "min_notional",
            tradefog.db.types.ExactDecimal(precision=30, scale=18),
            nullable=True,
        ),
        sa.Column("settlement_asset_id", sa.Integer(), nullable=True),
        sa.Column(
            "is_active", sa.Boolean(), server_default=sa.true(), nullable=False
        ),
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.ForeignKeyConstraint(
            ["pair_id"],
            ["TradingPair.id"],
            name=op.f("fk_VenueInstrument_pair_id_TradingPair"),
        ),
        sa.ForeignKeyConstraint(
            ["settlement_asset_id"],
            ["Asset.id"],
            name=op.f("fk_VenueInstrument_settlement_asset_id_Asset"),
        ),
        sa.ForeignKeyConstraint(
            ["venue_id"],
            ["Venue.id"],
            name=op.f("fk_VenueInstrument_venue_id_Venue"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_VenueInstrument")),
    )
    with op.batch_alter_table("VenueInstrument", schema=None) as batch_op:
        batch_op.create_index(
            "venue_instrument_venue_exec_symbol_idx",
            ["venue_id", "exec_symbol"],
            unique=True,
        )
        batch_op.create_index(
            "venue_instrument_venue_pair_product_idx",
            ["venue_id", "pair_id", "product"],
            unique=True,
        )

    _ = op.create_table(
        "Wallet",
        sa.Column("profile_id", sa.Integer(), nullable=False),
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.ForeignKeyConstraint(
            ["profile_id"],
            ["TradingProfile.id"],
            name=op.f("fk_Wallet_profile_id_TradingProfile"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_Wallet")),
        sa.UniqueConstraint("profile_id", name=op.f("uq_Wallet_profile_id")),
    )
    _ = op.create_table(
        "Trade",
        sa.Column("profile_id", sa.Integer(), nullable=False),
        sa.Column("strategy_id", sa.Integer(), nullable=False),
        sa.Column("venue_instrument_id", sa.Integer(), nullable=False),
        sa.Column("trade_date", sa.Date(), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "draft",
                "pending_entry",
                "open",
                "closed",
                "cancelled",
                name="trade_status",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column(
            "direction",
            sa.Enum(
                "long",
                "short",
                name="direction",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column(
            "draft_context",
            sa.JSON(),
            server_default=sa.text("'{}'"),
            nullable=False,
        ),
        sa.Column("description_markdown", sa.Text(), nullable=True),
        sa.Column("review_completed_at", sa.DateTime(), nullable=True),
        sa.Column(
            "realized_pnl",
            tradefog.db.types.ExactDecimal(precision=30, scale=18),
            nullable=True,
        ),
        sa.Column(
            "actual_exit_price",
            tradefog.db.types.ExactDecimal(precision=30, scale=18),
            nullable=True,
        ),
        sa.Column(
            "total_commission",
            tradefog.db.types.ExactDecimal(precision=30, scale=18),
            nullable=True,
        ),
        sa.Column(
            "funding_result",
            tradefog.db.types.ExactDecimal(precision=30, scale=18),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.ForeignKeyConstraint(
            ["profile_id"],
            ["TradingProfile.id"],
            name=op.f("fk_Trade_profile_id_TradingProfile"),
        ),
        sa.ForeignKeyConstraint(
            ["strategy_id"],
            ["TradingStrategy.id"],
            name=op.f("fk_Trade_strategy_id_TradingStrategy"),
        ),
        sa.ForeignKeyConstraint(
            ["venue_instrument_id"],
            ["VenueInstrument.id"],
            name=op.f("fk_Trade_venue_instrument_id_VenueInstrument"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_Trade")),
    )
    _ = op.create_table(
        "WalletAsset",
        sa.Column("wallet_id", sa.Integer(), nullable=False),
        sa.Column("venue_wallet_asset_id", sa.Integer(), nullable=False),
        sa.Column(
            "risk_stop_capital",
            tradefog.db.types.ExactDecimal(precision=30, scale=18),
            nullable=True,
        ),
        sa.Column(
            "status",
            sa.Enum(
                "active",
                "at_risk",
                "risk_stopped",
                name="wallet_asset_status",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column(
            "is_archived",
            sa.Boolean(),
            server_default=sa.false(),
            nullable=False,
        ),
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.ForeignKeyConstraint(
            ["venue_wallet_asset_id"],
            ["VenueWalletAsset.id"],
            name=op.f("fk_WalletAsset_venue_wallet_asset_id_VenueWalletAsset"),
        ),
        sa.ForeignKeyConstraint(
            ["wallet_id"],
            ["Wallet.id"],
            name=op.f("fk_WalletAsset_wallet_id_Wallet"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_WalletAsset")),
    )
    with op.batch_alter_table("WalletAsset", schema=None) as batch_op:
        batch_op.create_index(
            "wallet_asset_wallet_venue_asset_idx",
            ["wallet_id", "venue_wallet_asset_id"],
            unique=True,
        )

    _ = op.create_table(
        "StrategyCapital",
        sa.Column("strategy_id", sa.Integer(), nullable=False),
        sa.Column("wallet_asset_id", sa.Integer(), nullable=False),
        sa.Column(
            "capital",
            tradefog.db.types.ExactDecimal(precision=30, scale=18),
            nullable=False,
        ),
        sa.Column(
            "is_archived",
            sa.Boolean(),
            server_default=sa.false(),
            nullable=False,
        ),
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.ForeignKeyConstraint(
            ["strategy_id"],
            ["TradingStrategy.id"],
            name=op.f("fk_StrategyCapital_strategy_id_TradingStrategy"),
        ),
        sa.ForeignKeyConstraint(
            ["wallet_asset_id"],
            ["WalletAsset.id"],
            name=op.f("fk_StrategyCapital_wallet_asset_id_WalletAsset"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_StrategyCapital")),
    )
    with op.batch_alter_table("StrategyCapital", schema=None) as batch_op:
        batch_op.create_index(
            "strategy_capital_strategy_wallet_asset_idx",
            ["strategy_id", "wallet_asset_id"],
            unique=True,
        )

    _ = op.create_table(
        "TradeSnapshot",
        sa.Column("trade_id", sa.Integer(), nullable=False),
        sa.Column(
            "planned_entry",
            tradefog.db.types.ExactDecimal(precision=30, scale=18),
            nullable=False,
        ),
        sa.Column(
            "planned_stop",
            tradefog.db.types.ExactDecimal(precision=30, scale=18),
            nullable=False,
        ),
        sa.Column(
            "planned_take_profit",
            tradefog.db.types.ExactDecimal(precision=30, scale=18),
            nullable=True,
        ),
        sa.Column(
            "quantity",
            tradefog.db.types.ExactDecimal(precision=30, scale=18),
            nullable=True,
        ),
        sa.Column(
            "reward_multiple",
            tradefog.db.types.ExactDecimal(precision=10, scale=6),
            nullable=True,
        ),
        sa.Column(
            "planned_risk_percent",
            tradefog.db.types.ExactDecimal(precision=10, scale=6),
            nullable=True,
        ),
        sa.Column(
            "planned_risk_amount",
            tradefog.db.types.ExactDecimal(precision=30, scale=18),
            nullable=True,
        ),
        sa.Column(
            "planned_notional",
            tradefog.db.types.ExactDecimal(precision=30, scale=18),
            nullable=True,
        ),
        sa.Column(
            "allocation_capital",
            tradefog.db.types.ExactDecimal(precision=30, scale=18),
            nullable=True,
        ),
        sa.Column(
            "risk_stop_capital",
            tradefog.db.types.ExactDecimal(precision=30, scale=18),
            nullable=True,
        ),
        sa.Column(
            "already_reserved_risk",
            tradefog.db.types.ExactDecimal(precision=30, scale=18),
            nullable=True,
        ),
        sa.Column(
            "remaining_risk_capacity",
            tradefog.db.types.ExactDecimal(precision=30, scale=18),
            nullable=True,
        ),
        sa.Column("deposit_floor_breach", sa.Boolean(), nullable=True),
        sa.Column(
            "wallet_balance",
            tradefog.db.types.ExactDecimal(precision=30, scale=18),
            nullable=True,
        ),
        sa.Column(
            "wallet_reserved",
            tradefog.db.types.ExactDecimal(precision=30, scale=18),
            nullable=True,
        ),
        sa.Column(
            "wallet_available",
            tradefog.db.types.ExactDecimal(precision=30, scale=18),
            nullable=True,
        ),
        sa.Column(
            "atr_value",
            tradefog.db.types.ExactDecimal(precision=30, scale=18),
            nullable=True,
        ),
        sa.Column(
            "atr_source",
            sa.Enum(
                "auto",
                "manual",
                name="atr_source",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=True,
        ),
        sa.Column("atr_contributing_date", sa.Date(), nullable=True),
        sa.Column("atr_observation_time", sa.DateTime(), nullable=True),
        sa.Column("atr_stale", sa.Boolean(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.ForeignKeyConstraint(
            ["trade_id"],
            ["Trade.id"],
            name=op.f("fk_TradeSnapshot_trade_id_Trade"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_TradeSnapshot")),
        sa.UniqueConstraint(
            "trade_id", name=op.f("uq_TradeSnapshot_trade_id")
        ),
    )
    _ = op.create_table(
        "WalletOperation",
        sa.Column("wallet_asset_id", sa.Integer(), nullable=False),
        sa.Column(
            "kind",
            sa.Enum(
                "deposit",
                "withdrawal",
                name="wallet_operation_kind",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column(
            "amount",
            tradefog.db.types.ExactDecimal(precision=30, scale=18),
            nullable=False,
        ),
        sa.Column("note", sa.String(length=255), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.ForeignKeyConstraint(
            ["wallet_asset_id"],
            ["WalletAsset.id"],
            name=op.f("fk_WalletOperation_wallet_asset_id_WalletAsset"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_WalletOperation")),
    )


def downgrade() -> None:
    """Reverse this schema revision."""
    op.drop_table("WalletOperation")
    op.drop_table("TradeSnapshot")
    with op.batch_alter_table("StrategyCapital", schema=None) as batch_op:
        batch_op.drop_index("strategy_capital_strategy_wallet_asset_idx")

    op.drop_table("StrategyCapital")
    with op.batch_alter_table("WalletAsset", schema=None) as batch_op:
        batch_op.drop_index("wallet_asset_wallet_venue_asset_idx")

    op.drop_table("WalletAsset")
    op.drop_table("Trade")
    op.drop_table("Wallet")
    with op.batch_alter_table("VenueInstrument", schema=None) as batch_op:
        batch_op.drop_index("venue_instrument_venue_pair_product_idx")
        batch_op.drop_index("venue_instrument_venue_exec_symbol_idx")

    op.drop_table("VenueInstrument")
    op.drop_table("TradingStrategy")
    with op.batch_alter_table("VenueWalletAsset", schema=None) as batch_op:
        batch_op.drop_index("venue_wallet_asset_venue_asset_idx")

    op.drop_table("VenueWalletAsset")
    op.drop_table("TradingProfile")
    with op.batch_alter_table("TradingPair", schema=None) as batch_op:
        batch_op.drop_index("trading_pair_base_quote_idx")

    op.drop_table("TradingPair")
    op.drop_table("users")
    with op.batch_alter_table("Venue", schema=None) as batch_op:
        batch_op.drop_index("venue_name_idx")

    op.drop_table("Venue")
    with op.batch_alter_table("Asset", schema=None) as batch_op:
        batch_op.drop_index("asset_symbol_idx")

    op.drop_table("Asset")

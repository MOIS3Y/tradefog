"""Regression checks for exact money, ownership and migrated persistence."""

from collections.abc import AsyncIterator, Iterator
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import cast

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from sqlalchemy import inspect, select
from sqlalchemy.engine import Connection
from sqlalchemy.exc import IntegrityError, StatementError
from sqlalchemy.ext.asyncio import AsyncSession

from tradefog.config import get_settings
from tradefog.config.database import DatabaseSettings, SQLiteSettings
from tradefog.db.base import Base
from tradefog.db.models import (
    Asset,
    StrategyCapital,
    Trade,
    TradeSnapshot,
    TradingPair,
    TradingProfile,
    TradingStrategy,
    User,
    Venue,
    VenueInstrument,
    VenueWalletAsset,
    Wallet,
    WalletAsset,
    WalletOperation,
)
from tradefog.db.scoping import JournalModel, owned_select
from tradefog.db.session import Database
from tradefog.domain.enums import (
    AssetType,
    Direction,
    ProductKind,
    StrategyStatus,
    TradeStatus,
    WalletAssetStatus,
    WalletOperationKind,
)

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def migrated_path(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> Iterator[Path]:
    """Apply the real initial migration to an isolated SQLite database."""
    path = tmp_path / "journal.db"
    monkeypatch.setenv("TRADEFOG_DATABASE__ACTIVE", "sqlite")
    monkeypatch.setenv("TRADEFOG_DATABASE__SQLITE__PATH", str(path))
    get_settings.cache_clear()
    config = Config(str(ROOT / "alembic.ini"))
    command.upgrade(config, "head")
    try:
        yield path
    finally:
        get_settings.cache_clear()


@pytest.fixture
async def database(migrated_path: Path) -> AsyncIterator[Database]:
    """Provide the production transaction manager over the migrated DB."""
    database = Database(
        DatabaseSettings(
            sqlite=SQLiteSettings(path=migrated_path),
        )
    )
    try:
        yield database
    finally:
        await database.dispose()


async def seed_journal(
    session: AsyncSession,
    owner: User,
    venue: Venue,
    instrument: VenueInstrument,
    capability: VenueWalletAsset,
) -> dict[type[JournalModel], int]:
    """Create every journal entity for one of two independent owners."""
    profile = TradingProfile(owner=owner, venue=venue, name=owner.username)
    wallet = Wallet(profile=profile)
    asset = WalletAsset(
        wallet=wallet,
        venue_wallet_asset=capability,
        status=WalletAssetStatus.ACTIVE,
    )
    operation = WalletOperation(
        wallet_asset=asset,
        kind=WalletOperationKind.DEPOSIT,
        amount=Decimal("999999999999.123456789012345678"),
    )
    strategy = TradingStrategy(
        profile=profile,
        name="Test",
        risk_percent=Decimal("1.123456"),
        status=StrategyStatus.ACTIVE,
    )
    capital = StrategyCapital(
        strategy=strategy,
        wallet_asset=asset,
        capital=Decimal(100),
    )
    trade = Trade(
        profile=profile,
        strategy=strategy,
        venue_instrument=instrument,
        trade_date=date(2026, 9, 7),
        status=TradeStatus.PENDING_ENTRY,
        direction=Direction.LONG,
    )
    snapshot = TradeSnapshot(
        trade=trade,
        planned_entry=Decimal("0.000000000000000002"),
        planned_stop=Decimal("0.000000000000000001"),
    )
    records = [
        profile,
        wallet,
        asset,
        operation,
        strategy,
        capital,
        trade,
        snapshot,
    ]
    session.add_all(records)
    await session.flush()
    return {type(record): record.id for record in records}


async def test_owner_scoping_and_exact_money(database: Database) -> None:
    """All eight journal paths exclude another owner's data by ID too."""
    async with database.session() as session:
        alice = User(username="alice", password="hash")
        bob = User(username="bob", password="hash", is_staff=True)
        venue = Venue(name="Test")
        base = Asset(symbol="BTC", asset_type=AssetType.CRYPTO)
        quote = Asset(symbol="USD", asset_type=AssetType.FIAT)
        pair = TradingPair(base=base, quote=quote, canonical_symbol="BTC/USD")
        instrument = VenueInstrument(
            venue=venue,
            pair=pair,
            product=ProductKind.SPOT,
            exec_symbol="BTCUSD",
            price_step=Decimal("0.01"),
            qty_step=Decimal("0.00000001"),
        )
        capability = VenueWalletAsset(venue=venue, asset=quote)
        first = await seed_journal(
            session,
            alice,
            venue,
            instrument,
            capability,
        )
        second = await seed_journal(
            session,
            bob,
            venue,
            instrument,
            capability,
        )
        alice_id, bob_id = alice.id, bob.id

    async with database.session() as session:
        for model, first_id in first.items():
            rows = (await session.scalars(owned_select(model, alice_id))).all()
            assert [row.id for row in rows] == [first_id]
            assert (
                await session.scalar(
                    owned_select(model, alice_id).where(
                        model.id == second[model]
                    ),
                )
                is None
            )
            assert await session.scalar(owned_select(model, -1)) is None
            bob_rows = (
                await session.scalars(
                    owned_select(model, bob_id),
                )
            ).all()
            assert [row.id for row in bob_rows] == [second[model]]
        operation = await session.get(WalletOperation, first[WalletOperation])
        snapshot = await session.get(TradeSnapshot, first[TradeSnapshot])
        assert operation is not None and snapshot is not None
        assert operation.amount == Decimal("999999999999.123456789012345678")
        assert snapshot.planned_stop == Decimal("0.000000000000000001")
        assert operation.created_at is not None

    with pytest.raises(ValueError, match="Unsupported"):
        _ = owned_select(cast(type[JournalModel], Asset), alice_id)


async def test_transaction_rollback_and_foreign_keys(
    database: Database,
) -> None:
    """A failed unit of work leaves no rows; SQLite rejects orphan links."""
    with pytest.raises(RuntimeError, match="abort"):
        async with database.session() as session:
            session.add(User(username="rolled-back", password="hash"))
            await session.flush()
            raise RuntimeError("abort")
    async with database.session() as session:
        assert await session.scalar(select(User)) is None
    with pytest.raises(IntegrityError):
        async with database.session() as session:
            session.add(Wallet(profile_id=999))


@pytest.mark.parametrize(
    "value",
    [
        Decimal(1000000000000),
        Decimal("0.0000000000000000001"),
        Decimal("NaN"),
        Decimal("Infinity"),
        0.1,
    ],
)
async def test_invalid_money_is_rejected(
    database: Database,
    value: object,
) -> None:
    """Reject rounding, overflow and float inputs before database writes."""
    with pytest.raises(StatementError, match="Decimal|Financial"):
        async with database.session() as session:
            session.add(
                WalletOperation(
                    wallet_asset_id=999,
                    kind=WalletOperationKind.DEPOSIT,
                    amount=value,
                )
            )


async def test_migration_matches_models(database: Database) -> None:
    """The committed revision creates all tables with no metadata drift."""

    def check_schema(connection: Connection) -> None:
        """Compare the migrated schema to ORM declarations."""
        tables = set(inspect(connection).get_table_names())
        assert tables == set(Base.metadata.tables) | {"alembic_version"}
        assert (
            compare_metadata(
                MigrationContext.configure(connection),
                Base.metadata,
            )
            == []
        )

    async with database.engine.connect() as connection:
        await connection.run_sync(check_schema)


def test_migration_downgrade_and_reapply(migrated_path: Path) -> None:
    """The initial revision can be reversed and applied again."""
    import sqlite3

    config = Config(str(ROOT / "alembic.ini"))
    command.downgrade(config, "base")
    with sqlite3.connect(migrated_path) as connection:
        tables = connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'",
        ).fetchall()
    assert tables == [("alembic_version",)]
    command.upgrade(config, "head")

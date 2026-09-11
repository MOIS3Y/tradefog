"""Static baseline, ownership and exact financial storage checks."""

from decimal import Decimal
from typing import Any, cast

from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from fastapi import FastAPI
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.engine import Connection

from tests.test_trade_flow import post, setup_market
from tradefog.db.base import Base
from tradefog.db.models import TradingAsset, WalletOperation
from tradefog.db.scoping import owned_select
from tradefog.db.session import Database


async def test_migration_matches_models(profile_app: FastAPI) -> None:
    """The static migration matches current model metadata."""
    database = cast(Database, profile_app.state.database)

    def compare(sync: Connection) -> list[Any]:
        """Compare the migrated schema using the actual dialect."""
        return compare_metadata(
            MigrationContext.configure(sync), Base.metadata
        )

    async with database.engine.connect() as connection:
        differences = await connection.run_sync(compare)
    assert differences == []


async def test_exact_virtual_money_and_asset_owner_scoping(
    profile_client: AsyncClient, profile_app: FastAPI
) -> None:
    """Read exact decimals and scope new assets through their profile."""
    market = await setup_market(profile_client)
    await post(
        profile_client,
        market["root"] + f"/assets/{market['quote']['id']}/operations",
        {
            "kind": "deposit",
            "amount": "0.123456789123456789",
        },
    )
    async with profile_app.state.database.session() as session:
        amounts = (await session.scalars(select(WalletOperation.amount))).all()
        assert Decimal("0.123456789123456789") in amounts
        assert (
            len((await session.scalars(owned_select(TradingAsset, 1))).all())
            == 2
        )
        assert not (await session.scalars(owned_select(TradingAsset, 2))).all()

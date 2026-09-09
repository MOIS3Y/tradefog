"""Integration tests for JWT authentication and shared catalog endpoints."""

import subprocess
import sys
from collections.abc import AsyncIterator, Iterator
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import jwt
import pytest
from alembic import command
from alembic.config import Config
from httpx import ASGITransport, AsyncClient
from pydantic import SecretStr
from sqlalchemy import select

from tradefog.api.security import decode_token, hash_password
from tradefog.config import get_settings
from tradefog.config.authentication import AuthenticationSettings
from tradefog.config.database import DatabaseSettings, SQLiteSettings
from tradefog.config.root import Settings
from tradefog.db.models import (
    Asset,
    Trade,
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
from tradefog.db.session import Database
from tradefog.domain.enums import (
    AssetType,
    Direction,
    ProductKind,
    StrategyStatus,
    TradeStatus,
)
from tradefog.main import create_app

ROOT = Path(__file__).resolve().parents[1]


async def test_profile_pages_search_filter_and_scope(
    client: AsyncClient,
    database_path: Path,
) -> None:
    """Filter all owned profiles before counting and stable pagination."""
    database = Database(
        DatabaseSettings(sqlite=SQLiteSettings(path=database_path))
    )
    async with database.session() as session:
        owner = await session.scalar(
            select(User).where(User.username == "alice")
        )
        assert owner is not None
        venue = Venue(name="Биржа", market_data_provider="none")
        session.add(venue)
        await session.flush()
        session.add_all(
            [
                TradingProfile(
                    owner_id=owner.id,
                    venue_id=venue.id,
                    name=name,
                    is_archived=name == "CCC",
                )
                for name in ("BBB", "AAA", "CCC", "A_B")
            ]
        )
    await database.dispose()
    headers = await login_headers(client, "alice", "alice-password-123")
    path = "/api/v1/profiles"
    for page, names in ((1, ["AAA", "A_B"]), (2, ["BBB"]), (3, [])):
        response = await client.get(
            path,
            headers=headers,
            params={
                "page": page,
                "page_size": 2,
                "visibility": "active",
                "q": "БИРЖА",
            },
        )
        assert response.status_code == 200, response.text
        data = response.json()
        assert data["total"] == 3
        assert [item["name"] for item in data["items"]] == names
    archived = await client.get(
        path, headers=headers, params={"visibility": "archived"}
    )
    assert [item["name"] for item in archived.json()["items"]] == ["CCC"]
    literal = await client.get(path, headers=headers, params={"q": "_"})
    assert literal.json()["total"] == 1
    other = await login_headers(client, "regular", "regular-password-123")
    assert (await client.get(path, headers=other)).json()["total"] == 0
    for params in ({"page": 0}, {"page_size": 101}, {"sort": "owner_id"}):
        assert (
            await client.get(path, headers=headers, params=params)
        ).status_code == 422


async def test_wallet_operation_pages_are_stable_and_private(
    client: AsyncClient,
    database_path: Path,
) -> None:
    """Page equal-time ledger facts without leaking another owner's data."""
    database = Database(
        DatabaseSettings(sqlite=SQLiteSettings(path=database_path))
    )
    async with database.session() as session:
        owner = await session.scalar(
            select(User).where(User.username == "alice")
        )
        assert owner is not None
        asset = Asset(symbol="USD", asset_type=AssetType.FIAT)
        venue = Venue(name="Wallet venue", market_data_provider="none")
        session.add_all([asset, venue])
        await session.flush()
        capability = VenueWalletAsset(venue_id=venue.id, asset_id=asset.id)
        profile = TradingProfile(
            owner_id=owner.id, venue_id=venue.id, name="Ledger"
        )
        session.add_all([capability, profile])
        await session.flush()
        wallet = Wallet(profile_id=profile.id)
        session.add(wallet)
        await session.flush()
        balance = WalletAsset(
            wallet_id=wallet.id,
            venue_wallet_asset_id=capability.id,
            status="active",
        )
        session.add(balance)
        await session.flush()
        identifier = balance.id
        session.add_all(
            [
                WalletOperation(
                    wallet_asset_id=identifier,
                    kind="deposit",
                    amount=Decimal(i),
                    created_at=datetime(2026, 9, 9, tzinfo=UTC),
                )
                for i in range(1, 4)
            ]
        )
    await database.dispose()
    headers = await login_headers(client, "alice", "alice-password-123")
    path = f"/api/v1/profiles/wallet-assets/{identifier}/operations"
    ids: list[int] = []
    for page, amounts in ((1, [3, 2]), (2, [1]), (3, [])):
        response = await client.get(
            path, headers=headers, params={"page": page, "page_size": 2}
        )
        assert response.status_code == 200, response.text
        data = response.json()
        assert data["total"] == 3
        assert data["page"] == page
        assert [Decimal(x["amount"]) for x in data["items"]] == amounts
        ids.extend(x["id"] for x in data["items"])
    assert len(set(ids)) == 3
    for params in ({"page": 0}, {"page_size": 101}):
        assert (
            await client.get(path, headers=headers, params=params)
        ).status_code == 422
    other = await login_headers(client, "regular", "regular-password-123")
    assert (await client.get(path, headers=other)).status_code == 404


async def test_server_pages_filter_before_sorting_and_counting(
    client: AsyncClient,
) -> None:
    """Catalog searches cover later pages and escape SQL wildcards."""
    staff = await login_headers(client, "staff", "staff-password-123")
    for symbol in ("CCC", "AAA", "BBB", "A_B", "A%B"):
        response = await client.post(
            "/api/v1/catalog/assets",
            headers=staff,
            json={"symbol": symbol, "asset_type": "crypto"},
        )
        assert response.status_code == 201
    response = await client.get(
        "/api/v1/catalog/assets",
        params={"page_size": 2, "page": 2, "sort": "symbol", "order": "desc"},
    )
    assert response.status_code == 200, response.text
    assert response.json()["total"] == 5
    assert [x["symbol"] for x in response.json()["items"]] == ["A_B", "AAA"]
    for term in ("_", "%"):
        result = await client.get("/api/v1/catalog/assets", params={"q": term})
        assert result.json()["total"] == 1
    result = await client.get("/api/v1/catalog/assets", params={"q": "ccc"})
    assert result.json()["items"][0]["symbol"] == "CCC"
    assert (
        await client.get(
            "/api/v1/catalog/assets",
            params={"page": 99},
        )
    ).json()["items"] == []
    for params in ({"sort": "password"}, {"page": 0}, {"page_size": 101}):
        assert (
            await client.get(
                "/api/v1/catalog/assets",
                params=params,
            )
        ).status_code == 422


async def test_trade_pages_preserve_owner_review_and_rating_semantics(
    client: AsyncClient,
    database_path: Path,
) -> None:
    """Counts and ordering stay owner-scoped and null ratings stay last."""
    database = Database(
        DatabaseSettings(
            sqlite=SQLiteSettings(path=database_path),
        )
    )
    async with database.session() as session:
        alice = await session.scalar(
            select(User).where(User.username == "alice")
        )
        other = await session.scalar(
            select(User).where(User.username == "regular")
        )
        assert alice is not None and other is not None
        base = Asset(symbol="BTC", asset_type=AssetType.CRYPTO)
        quote = Asset(symbol="USD", asset_type=AssetType.FIAT)
        venue = Venue(name="Exchange", market_data_provider="none")
        session.add_all([base, quote, venue])
        await session.flush()
        pair = TradingPair(
            base_id=base.id, quote_id=quote.id, canonical_symbol="BTC/USD"
        )
        session.add(pair)
        await session.flush()
        instrument = VenueInstrument(
            venue_id=venue.id,
            pair_id=pair.id,
            product=ProductKind.SPOT,
            exec_symbol="BTCUSD",
            price_step=Decimal(1),
            qty_step=Decimal("0.01"),
        )
        session.add(instrument)
        await session.flush()
        for owner in (alice, other):
            profile = TradingProfile(
                owner_id=owner.id, venue_id=venue.id, name="Журнал"
            )
            session.add(profile)
            await session.flush()
            strategy = TradingStrategy(
                profile_id=profile.id,
                name="Breakout",
                risk_percent=Decimal(1),
                status=StrategyStatus.ACTIVE,
            )
            session.add(strategy)
            await session.flush()
            for rating, status, reviewed in (
                (None, TradeStatus.DRAFT, False),
                (None, TradeStatus.CLOSED, False),
                (3, TradeStatus.CLOSED, False),
                (9, TradeStatus.CLOSED, True),
                (9, TradeStatus.OPEN, False),
            ):
                session.add(
                    Trade(
                        profile_id=profile.id,
                        strategy_id=strategy.id,
                        venue_instrument_id=instrument.id,
                        trade_date=date(2026, 9, 9),
                        direction=Direction.LONG,
                        status=status,
                        quality_rating=rating,
                        review_completed_at=datetime(2026, 9, 10, tzinfo=UTC)
                        if reviewed
                        else None,
                    )
                )
    await database.dispose()
    headers = await login_headers(client, "alice", "alice-password-123")
    for order, expected in (
        ("asc", [3, 9, 9, None, None]),
        ("desc", [9, 9, 3, None, None]),
    ):
        rows = []
        for page in (1, 2, 3):
            result = await client.get(
                "/api/v1/trades",
                headers=headers,
                params={
                    "sort": "quality_rating",
                    "order": order,
                    "page_size": 2,
                    "page": page,
                    "q": "breakout",
                },
            )
            assert result.status_code == 200, result.text
            assert result.json()["total"] == 5
            rows.extend(result.json()["items"])
        assert [row["quality_rating"] for row in rows] == expected
        assert len({row["id"] for row in rows}) == 5
        assert all("snapshot" not in row and "plan" not in row for row in rows)
        assert all(row["settlement_symbol"] == "USD" for row in rows)
    for params, total in (
        ({"review": "reviewed"}, 1),
        ({"review": "unreviewed"}, 2),
        ({"review": "unreviewed", "rated": "false"}, 1),
        ({"rated": "true"}, 3),
        ({"q": "жУРнал"}, 5),
        ({"trade_status": "open"}, 1),
        ({"date_from": "2026-09-10"}, 0),
    ):
        result = await client.get(
            "/api/v1/trades", headers=headers, params=params
        )
        assert result.status_code == 200, result.text
        assert result.json()["total"] == total
    invalid = await client.get(
        "/api/v1/trades",
        headers=headers,
        params={
            "date_from": "2026-09-10",
            "date_to": "2026-09-01",
        },
    )
    assert invalid.status_code == 422


@pytest.fixture
def database_path(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> Iterator[Path]:
    """Create an isolated SQLite database using the production migration."""
    path = tmp_path / "api.db"
    monkeypatch.setenv("TRADEFOG_DATABASE__ACTIVE", "sqlite")
    monkeypatch.setenv("TRADEFOG_DATABASE__SQLITE__PATH", str(path))
    get_settings.cache_clear()
    command.upgrade(Config(str(ROOT / "alembic.ini")), "head")
    try:
        yield path
    finally:
        get_settings.cache_clear()


@pytest.fixture
async def client(database_path: Path) -> AsyncIterator[AsyncClient]:
    """Run the complete API against a migrated database with a test JWT key."""
    settings = Settings(
        database=DatabaseSettings(sqlite=SQLiteSettings(path=database_path)),
        authentication=AuthenticationSettings(
            jwt_secret_key=SecretStr(
                "test-only-signing-key-with-32-characters"
            ),
        ),
    )
    app = create_app(settings)
    async with app.router.lifespan_context(app):
        async with app.state.database.session() as session:
            session.add(
                User(
                    username="staff",
                    password=hash_password("staff-password-123"),
                    is_staff=True,
                )
            )
            session.add(
                User(
                    username="alice",
                    password=hash_password("alice-password-123"),
                )
            )
            session.add(
                User(
                    username="regular",
                    password=hash_password("regular-password-123"),
                )
            )
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as api_client:
            yield api_client


async def login_headers(
    client: AsyncClient, username: str, password: str
) -> dict[str, str]:
    """Authenticate a provisioned account and return bearer token headers."""
    response = await client.post(
        "/api/v1/auth/token",
        data={"username": username, "password": password},
    )
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


async def staff_headers(client: AsyncClient) -> dict[str, str]:
    """Authenticate the fixture's pre-provisioned staff account."""
    response = await client.post(
        "/api/v1/auth/token",
        data={"username": "staff", "password": "staff-password-123"},
    )
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


async def test_tokens_and_disabled_accounts(
    client: AsyncClient,
    database_path: Path,
) -> None:
    """JWTs authenticate active users, distinguish refresh and honor disabling."""
    headers = await login_headers(client, "alice", "alice-password-123")
    me = await client.get("/api/v1/auth/me", headers=headers)
    assert me.status_code == 200
    assert me.json() == {
        "id": 2,
        "username": "alice",
        "is_staff": False,
        "is_active": True,
    }
    invalid = await client.post(
        "/api/v1/auth/token",
        data={"username": "alice", "password": "wrong-password"},
    )
    assert invalid.status_code == 401

    login = await client.post(
        "/api/v1/auth/token",
        data={"username": "alice", "password": "alice-password-123"},
    )
    refresh = login.json()["refresh_token"]
    refreshed = await client.post(
        "/api/v1/auth/refresh",
        json={
            "refresh_token": refresh,
        },
    )
    assert refreshed.status_code == 200
    wrong_kind = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {refresh}"},
    )
    assert wrong_kind.status_code == 401

    database = Database(
        DatabaseSettings(
            sqlite=SQLiteSettings(path=database_path),
        )
    )
    try:
        async with database.session() as session:
            user = await session.get(User, me.json()["id"])
            assert user is not None
            user.is_active = False
        assert (
            await client.get(
                "/api/v1/auth/me",
                headers=headers,
            )
        ).status_code == 401
        assert (
            await client.post(
                "/api/v1/auth/refresh",
                json={"refresh_token": refresh},
            )
        ).status_code == 401
    finally:
        await database.dispose()


@pytest.mark.parametrize(
    "claims",
    [
        {"sub": "1", "type": "access"},
        {"sub": "1", "type": "access", "iat": 1, "exp": 2, "jti": "test"},
        {
            "sub": "99999999999999999999999",
            "type": "access",
            "iat": 1,
            "exp": 4102444800,
            "jti": "test",
        },
        {
            "sub": "1",
            "type": "refresh",
            "iat": 1,
            "exp": 4102444800,
            "jti": "test",
        },
    ],
)
def test_invalid_token_claims(claims: dict[str, str | int]) -> None:
    """Reject incomplete, expired, wrong-purpose and unbounded-subject JWTs."""
    settings = AuthenticationSettings(jwt_secret_key=SecretStr("x" * 32))
    token = jwt.encode(claims, "x" * 32, algorithm="HS256")
    assert decode_token(token, "access", settings) is None


def test_standalone_alembic_metadata(database_path: Path) -> None:
    """A fresh Alembic process must register all models before comparison."""
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "check"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert database_path.exists()
    assert result.returncode == 0, result.stdout + result.stderr


async def test_catalog_patch_preserves_referenced_identity(
    client: AsyncClient,
) -> None:
    """Reject required nulls and identity changes that alter related records."""
    headers = await staff_headers(client)
    base = (
        await client.post(
            "/api/v1/catalog/assets",
            headers=headers,
            json={"symbol": "BTC", "asset_type": "crypto"},
        )
    ).json()
    quote = (
        await client.post(
            "/api/v1/catalog/assets",
            headers=headers,
            json={"symbol": "USD", "asset_type": "fiat"},
        )
    ).json()
    pair = await client.post(
        "/api/v1/catalog/pairs",
        headers=headers,
        json={"base_id": base["id"], "quote_id": quote["id"]},
    )
    assert pair.status_code == 201
    changed = await client.patch(
        f"/api/v1/catalog/assets/{base['id']}",
        headers=headers,
        json={"symbol": "ETH"},
    )
    assert changed.status_code == 409
    invalid = await client.patch(
        f"/api/v1/catalog/assets/{base['id']}",
        headers=headers,
        json={"symbol": None},
    )
    assert invalid.status_code == 422
    cleared = await client.patch(
        f"/api/v1/catalog/assets/{base['id']}",
        headers=headers,
        json={"name": None},
    )
    assert cleared.status_code == 200
    assert cleared.json()["symbol"] == "BTC"
    venue = (
        await client.post(
            "/api/v1/catalog/venues",
            headers=headers,
            json={"name": "Test"},
        )
    ).json()
    instrument = await client.post(
        f"/api/v1/catalog/venues/{venue['id']}/instruments",
        headers=headers,
        json={
            "pair_id": pair.json()["id"],
            "product": "spot",
            "exec_symbol": "BTCUSD",
            "price_step": "0.1",
            "qty_step": "1",
        },
    )
    assert instrument.status_code == 201
    changed_pair = await client.patch(
        f"/api/v1/catalog/pairs/{pair.json()['id']}",
        headers=headers,
        json={"base_id": quote["id"], "quote_id": base["id"]},
    )
    assert changed_pair.status_code == 409
    invalid_flag = await client.patch(
        f"/api/v1/catalog/venues/{venue['id']}",
        headers=headers,
        json={"is_active": None},
    )
    assert invalid_flag.status_code == 422


async def test_catalog_is_public_read_and_staff_write(
    client: AsyncClient,
) -> None:
    """Only staff can maintain the complete shared catalog graph."""
    regular_headers = await login_headers(
        client,
        "regular",
        "regular-password-123",
    )
    denied = await client.post(
        "/api/v1/catalog/assets",
        headers=regular_headers,
        json={"symbol": "BTC", "asset_type": "crypto"},
    )
    assert denied.status_code == 403
    unauthenticated = await client.post(
        "/api/v1/catalog/assets",
        json={"symbol": "BTC", "asset_type": "crypto"},
    )
    assert unauthenticated.status_code == 401
    staff = await staff_headers(client)

    base = await client.post(
        "/api/v1/catalog/assets",
        headers=staff,
        json={"symbol": " btc ", "name": "Bitcoin", "asset_type": "crypto"},
    )
    quote = await client.post(
        "/api/v1/catalog/assets",
        headers=staff,
        json={"symbol": "USD", "asset_type": "fiat"},
    )
    assert base.status_code == quote.status_code == 201
    assert base.json()["symbol"] == "BTC"
    pair = await client.post(
        "/api/v1/catalog/pairs",
        headers=staff,
        json={"base_id": base.json()["id"], "quote_id": quote.json()["id"]},
    )
    assert pair.status_code == 201
    assert pair.json()["canonical_symbol"] == "BTC/USD"
    venue = await client.post(
        "/api/v1/catalog/venues",
        headers=staff,
        json={"name": "Bybit", "market_data_provider": "bybit"},
    )
    assert venue.status_code == 201
    instrument = await client.post(
        f"/api/v1/catalog/venues/{venue.json()['id']}/instruments",
        headers=staff,
        json={
            "pair_id": pair.json()["id"],
            "product": "perpetual_future",
            "exec_symbol": "btcusd",
            "price_step": "0.01",
            "qty_step": "0.001",
            "settlement_asset_id": quote.json()["id"],
        },
    )
    wallet_asset = await client.post(
        f"/api/v1/catalog/venues/{venue.json()['id']}/wallet-assets",
        headers=staff,
        json={"asset_id": quote.json()["id"]},
    )
    assert instrument.status_code == wallet_asset.status_code == 201
    assert instrument.json()["exec_symbol"] == "BTCUSD"

    pairs = await client.get("/api/v1/catalog/pairs")
    instruments = await client.get(
        f"/api/v1/catalog/venues/{venue.json()['id']}/instruments",
    )
    capabilities = await client.get(
        f"/api/v1/catalog/venues/{venue.json()['id']}/wallet-assets",
    )
    assert (
        pairs.status_code
        == instruments.status_code
        == capabilities.status_code
        == 200
    )
    assert pairs.json()["items"] == [pair.json()]
    assert (
        instruments.json()["items"][0]["settlement_asset"]["symbol"] == "USD"
    )
    assert capabilities.json()["items"][0]["asset"]["symbol"] == "USD"
    for path, columns in (
        ("/api/v1/catalog/pairs", ("base", "quote", "type_relation")),
        ("/api/v1/catalog/instruments", ("pair", "settlement", "status")),
        (
            f"/api/v1/catalog/venues/{venue.json()['id']}/wallet-assets",
            ("type", "status"),
        ),
    ):
        for column in columns:
            ordered = await client.get(
                path, params={"sort": column, "order": "desc"}
            )
            assert ordered.status_code == 200, ordered.text
            assert ordered.json()["total"] == 1
    detail = await client.get(
        f"/api/v1/catalog/instruments/{instrument.json()['id']}"
    )
    assert detail.json()["pair"]["canonical_symbol"] == "BTC/USD"
    available = await client.get(
        "/api/v1/catalog/assets",
        params={"exclude_venue_id": venue.json()["id"]},
    )
    assert quote.json()["id"] not in [
        row["id"] for row in available.json()["items"]
    ]

    archived = await client.patch(
        f"/api/v1/catalog/venues/{venue.json()['id']}",
        headers=staff,
        json={"is_active": False},
    )
    assert archived.status_code == 200
    assert (
        await client.get(
            "/api/v1/catalog/venues?visibility=active",
        )
    ).json()["items"] == []
    assert (
        len(
            (
                await client.get(
                    "/api/v1/catalog/venues?visibility=all",
                )
            ).json()["items"]
        )
        == 1
    )

    in_use_venue = await client.delete(
        f"/api/v1/catalog/venues/{venue.json()['id']}",
        headers=staff,
    )
    assert in_use_venue.status_code == 409
    assert in_use_venue.json()["detail"]["code"] == "venue_in_use"

    unused_venue = await client.post(
        "/api/v1/catalog/venues",
        headers=staff,
        json={"name": "Paper broker"},
    )
    active_delete = await client.delete(
        f"/api/v1/catalog/venues/{unused_venue.json()['id']}",
        headers=staff,
    )
    assert active_delete.status_code == 409
    assert active_delete.json()["detail"]["code"] == "venue_not_archived"
    await client.patch(
        f"/api/v1/catalog/venues/{unused_venue.json()['id']}",
        headers=staff,
        json={"is_active": False},
    )
    deleted_venue = await client.delete(
        f"/api/v1/catalog/venues/{unused_venue.json()['id']}",
        headers=staff,
    )
    assert unused_venue.status_code == 201
    assert deleted_venue.status_code == 204

    active_instrument_delete = await client.delete(
        f"/api/v1/catalog/instruments/{instrument.json()['id']}",
        headers=staff,
    )
    active_capability_delete = await client.delete(
        f"/api/v1/catalog/wallet-assets/{wallet_asset.json()['id']}",
        headers=staff,
    )
    assert active_instrument_delete.status_code == 409
    assert (
        active_instrument_delete.json()["detail"]["code"]
        == "instrument_not_archived"
    )
    assert active_capability_delete.status_code == 409
    assert (
        active_capability_delete.json()["detail"]["code"]
        == "wallet_asset_not_archived"
    )
    await client.patch(
        f"/api/v1/catalog/instruments/{instrument.json()['id']}",
        headers=staff,
        json={"is_active": False},
    )
    await client.patch(
        f"/api/v1/catalog/wallet-assets/{wallet_asset.json()['id']}",
        headers=staff,
        json={"is_active": False},
    )
    assert (
        await client.delete(
            f"/api/v1/catalog/instruments/{instrument.json()['id']}",
            headers=staff,
        )
    ).status_code == 204
    assert (
        await client.delete(
            f"/api/v1/catalog/wallet-assets/{wallet_asset.json()['id']}",
            headers=staff,
        )
    ).status_code == 204


async def test_catalog_deletes_only_unused_assets_and_pairs(
    client: AsyncClient,
) -> None:
    """Allow staff cleanup without cascading through catalog references."""
    staff = await staff_headers(client)
    regular = await login_headers(
        client,
        "regular",
        "regular-password-123",
    )
    base = (
        await client.post(
            "/api/v1/catalog/assets",
            headers=staff,
            json={"symbol": "ETH", "asset_type": "crypto"},
        )
    ).json()
    quote = (
        await client.post(
            "/api/v1/catalog/assets",
            headers=staff,
            json={"symbol": "USDT", "asset_type": "crypto"},
        )
    ).json()
    unused = (
        await client.post(
            "/api/v1/catalog/assets",
            headers=staff,
            json={"symbol": "EUR", "asset_type": "fiat"},
        )
    ).json()
    pair = (
        await client.post(
            "/api/v1/catalog/pairs",
            headers=staff,
            json={"base_id": base["id"], "quote_id": quote["id"]},
        )
    ).json()
    unused_pair = (
        await client.post(
            "/api/v1/catalog/pairs",
            headers=staff,
            json={"base_id": quote["id"], "quote_id": base["id"]},
        )
    ).json()
    venue = (
        await client.post(
            "/api/v1/catalog/venues",
            headers=staff,
            json={"name": "Deletion test"},
        )
    ).json()
    instrument = await client.post(
        f"/api/v1/catalog/venues/{venue['id']}/instruments",
        headers=staff,
        json={
            "pair_id": pair["id"],
            "product": "spot",
            "exec_symbol": "ETHUSDT",
            "price_step": "0.01",
            "qty_step": "0.001",
        },
    )
    assert instrument.status_code == 201

    denied = await client.delete(
        f"/api/v1/catalog/assets/{unused['id']}",
        headers=regular,
    )
    assert denied.status_code == 403
    in_use = await client.delete(
        f"/api/v1/catalog/assets/{base['id']}",
        headers=staff,
    )
    assert in_use.status_code == 409
    assert in_use.json()["detail"]["code"] == "asset_in_use"

    pair_in_use = await client.delete(
        f"/api/v1/catalog/pairs/{pair['id']}",
        headers=staff,
    )
    assert pair_in_use.status_code == 409
    assert pair_in_use.json()["detail"]["code"] == "pair_in_use"
    deleted_pair = await client.delete(
        f"/api/v1/catalog/pairs/{unused_pair['id']}",
        headers=staff,
    )
    deleted_asset = await client.delete(
        f"/api/v1/catalog/assets/{unused['id']}",
        headers=staff,
    )
    assert deleted_pair.status_code == 204
    assert deleted_asset.status_code == 204

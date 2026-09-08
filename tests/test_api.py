"""Integration tests for JWT authentication and shared catalog endpoints."""

import subprocess
import sys
from collections.abc import AsyncIterator, Iterator
from pathlib import Path

import jwt
import pytest
from alembic import command
from alembic.config import Config
from httpx import ASGITransport, AsyncClient
from pydantic import SecretStr

from tradefog.api.security import decode_token, hash_password
from tradefog.config import get_settings
from tradefog.config.authentication import AuthenticationSettings
from tradefog.config.database import DatabaseSettings, SQLiteSettings
from tradefog.config.root import Settings
from tradefog.db.models import User
from tradefog.db.session import Database
from tradefog.main import create_app

ROOT = Path(__file__).resolve().parents[1]


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
    assert pairs.json() == [pair.json()]
    assert instruments.json()[0]["settlement_asset"]["symbol"] == "USD"
    assert capabilities.json()[0]["asset"]["symbol"] == "USD"

    archived = await client.patch(
        f"/api/v1/catalog/venues/{venue.json()['id']}",
        headers=staff,
        json={"is_active": False},
    )
    assert archived.status_code == 200
    assert (await client.get("/api/v1/catalog/venues")).json() == []
    assert (
        len(
            (
                await client.get(
                    "/api/v1/catalog/venues?active_only=false",
                )
            ).json()
        )
        == 1
    )


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

"""Fresh profile-schema application fixtures without external dependencies."""

from collections.abc import AsyncIterator, Iterator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from pydantic import SecretStr

from tradefog.api.security import hash_password
from tradefog.config import get_settings
from tradefog.config.authentication import AuthenticationSettings
from tradefog.config.database import DatabaseSettings, SQLiteSettings
from tradefog.config.media import MediaSettings
from tradefog.config.root import Settings
from tradefog.db.models import User
from tradefog.main import create_app

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def profile_db(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Iterator[Path]:
    """Apply the real baseline to an isolated SQLite database."""
    path = tmp_path / "profile.db"
    monkeypatch.setenv("TRADEFOG_DATABASE__ACTIVE", "sqlite")
    monkeypatch.setenv("TRADEFOG_DATABASE__SQLITE__PATH", str(path))
    get_settings.cache_clear()
    command.upgrade(Config(str(ROOT / "alembic.ini")), "head")
    try:
        yield path
    finally:
        get_settings.cache_clear()


@pytest.fixture
async def profile_app(profile_db: Path) -> AsyncIterator[FastAPI]:
    """Seed two users without an administrative market catalog."""
    app = create_app(
        Settings(
            database=DatabaseSettings(sqlite=SQLiteSettings(path=profile_db)),
            media=MediaSettings(root=profile_db.parent / "media"),
            authentication=AuthenticationSettings(
                jwt_secret_key=SecretStr(
                    "profile-tests-secret-key-at-least-32-characters"
                )
            ),
        )
    )
    async with app.router.lifespan_context(app):
        async with app.state.database.session() as session:
            session.add_all(
                [
                    User(username="alice", password=hash_password("secret")),
                    User(username="bob", password=hash_password("secret")),
                ]
            )
        yield app


@pytest.fixture
async def profile_client(profile_app: FastAPI) -> AsyncIterator[AsyncClient]:
    """Use actual authentication before accessing the journal."""
    async with AsyncClient(
        transport=ASGITransport(app=profile_app), base_url="http://test"
    ) as client:
        response = await client.post(
            "/api/v1/auth/token",
            data={"username": "alice", "password": "secret"},
        )
        assert response.status_code == 200, response.text
        client.headers["Authorization"] = (
            f"Bearer {response.json()['access_token']}"
        )
        yield client

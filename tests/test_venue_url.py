"""Optional venue navigation is validated independently of market providers."""

import sqlite3
from contextlib import closing
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from httpx import AsyncClient

from tests.test_trade_flow import post


def test_venue_url_migration_preserves_profiles(profile_db: Path) -> None:
    """Upgrade an existing baseline profile without rebuilding its records."""
    config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    command.downgrade(config, "0001")
    with closing(sqlite3.connect(profile_db)) as connection:
        connection.execute(
            "INSERT INTO users (id, username, password) VALUES (1, 'old', 'unused')"
        )
        connection.execute(
            "INSERT INTO TradingProfile (owner_id, venue_type, name) VALUES (1, 'manual', 'Existing')"
        )
        connection.commit()
    command.upgrade(config, "head")
    with closing(sqlite3.connect(profile_db)) as connection:
        assert connection.execute(
            "SELECT name, venue_url FROM TradingProfile"
        ).fetchone() == ("Existing", None)


@pytest.mark.parametrize("venue", ["manual", "bybit"])
async def test_profile_venue_url(
    profile_client: AsyncClient, venue: str
) -> None:
    """Create, edit, clear and owner-scope a browser link in either mode."""
    client = profile_client
    profile = await post(
        client,
        "/profiles",
        {
            "venue_type": venue,
            "name": "Linked",
            "venue_url": "https://regional.example.org/account?lang=ru",
        },
    )
    url = f"/api/v1/profiles/{profile['id']}"
    assert (
        profile["venue_url"] == "https://regional.example.org/account?lang=ru"
    )
    assert (await client.get(url)).json()["venue_url"] == profile["venue_url"]
    response = await client.patch(
        url, json={"venue_url": "http://broker.example.org"}
    )
    assert response.status_code == 200
    assert response.json()["venue_url"] == "http://broker.example.org/"
    for invalid in [
        "javascript:alert(1)",
        "data:text/html,x",
        "ftp://example.org",
        "/relative",
        "https://user:secret@example.org",
        "https://user@example.org",
        "https://example.org/" + "x" * 2048,
    ]:
        response = await client.patch(url, json={"venue_url": invalid})
        assert response.status_code == 422, response.text
    assert (await client.patch(url, json={"venue_url": ""})).json()[
        "venue_url"
    ] is None
    assert (await client.patch(url, json={"venue_url": None})).json()[
        "venue_url"
    ] is None
    token = await client.post(
        "/api/v1/auth/token", data={"username": "bob", "password": "secret"}
    )
    response = await client.patch(
        url,
        json={"venue_url": "https://other.example.org"},
        headers={"Authorization": f"Bearer {token.json()['access_token']}"},
    )
    assert response.status_code == 404

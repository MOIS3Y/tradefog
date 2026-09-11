"""Self-service metadata, language and credential revocation contracts."""

import sqlite3
from contextlib import closing
from pathlib import Path

import jwt
import pytest
from alembic import command
from alembic.config import Config
from fastapi import FastAPI
from httpx import AsyncClient

from tradefog.cli import update_user_password


async def test_account_settings(profile_client: AsyncClient) -> None:
    """Save only allowed fields and preserve owner isolation."""
    client = profile_client
    url = "/api/v1/auth/me"
    response = await client.patch(
        url,
        json={
            "first_name": " Alice ",
            "last_name": " Smith ",
            "email": "alice@example.com",
            "preferred_locale": "ru",
        },
    )
    assert response.status_code == 200
    assert response.json()["first_name"] == "Alice"
    assert response.json()["preferred_locale"] == "ru"
    assert "auth_version" not in response.json()
    assert "password" not in response.json()
    for body in [
        {"is_staff": True},
        {"username": "other"},
        {"auth_version": 3},
        {"preferred_locale": "de"},
        {"email": "invalid"},
    ]:
        assert (await client.patch(url, json=body)).status_code == 422
    response = await client.patch(
        url, json={"first_name": "  ", "email": None}
    )
    assert response.json()["first_name"] is None
    assert response.json()["email"] is None
    assert response.json()["preferred_locale"] == "ru"
    token = (
        await client.post(
            "/api/v1/auth/token",
            data={
                "username": "bob",
                "password": "secret",
            },
        )
    ).json()
    response = await client.get(
        url,
        headers={
            "Authorization": f"Bearer {token['access_token']}",
        },
    )
    assert response.json()["preferred_locale"] is None
    assert response.json()["last_name"] is None


@pytest.mark.parametrize("via_cli", [False, True])
async def test_password_revokes_sessions(
    profile_client: AsyncClient,
    profile_app: FastAPI,
    via_cli: bool,
) -> None:
    """Both entrypoints invalidate legacy and versioned access/refresh JWTs."""
    client = profile_client
    settings = profile_app.state.settings.authentication
    secret = settings.jwt_secret_key.get_secret_value()
    tokens = (
        await client.post(
            "/api/v1/auth/token",
            data={
                "username": "alice",
                "password": "secret",
            },
        )
    ).json()
    legacy = {}
    for kind in ("access_token", "refresh_token"):
        claims = jwt.decode(
            tokens[kind], secret, algorithms=[settings.algorithm]
        )
        claims.pop("ver")
        legacy[kind] = jwt.encode(claims, secret, algorithm=settings.algorithm)
    assert (
        await client.get(
            "/api/v1/auth/me",
            headers={
                "Authorization": f"Bearer {legacy['access_token']}",
            },
        )
    ).status_code == 200
    new_password = "new secure password"
    if via_cli:
        await update_user_password("alice", new_password)
    else:
        response = await client.post(
            "/api/v1/auth/password",
            json={
                "current_password": "wrong",
                "new_password": new_password,
            },
        )
        assert response.status_code == 400
        assert response.json()["detail"]["code"] == "current_password_invalid"
        assert (await client.get("/api/v1/auth/me")).status_code == 200
        for invalid in ["short", "x" * 129]:
            assert (
                await client.post(
                    "/api/v1/auth/password",
                    json={
                        "current_password": "secret",
                        "new_password": invalid,
                    },
                )
            ).status_code == 422
        response = await client.post(
            "/api/v1/auth/password",
            json={
                "current_password": "secret",
                "new_password": new_password,
            },
        )
        assert response.status_code == 204, response.text
    for pair in (tokens, legacy):
        assert (
            await client.get(
                "/api/v1/auth/me",
                headers={
                    "Authorization": f"Bearer {pair['access_token']}",
                },
            )
        ).status_code == 401
        assert (
            await client.post(
                "/api/v1/auth/refresh",
                json={
                    "refresh_token": pair["refresh_token"],
                },
            )
        ).status_code == 401
    assert (
        await client.post(
            "/api/v1/auth/token",
            data={
                "username": "alice",
                "password": "secret",
            },
        )
    ).status_code == 401
    response = await client.post(
        "/api/v1/auth/token",
        data={
            "username": "alice",
            "password": new_password,
        },
    )
    assert response.status_code == 200
    client.headers["Authorization"] = (
        f"Bearer {response.json()['access_token']}"
    )
    assert (await client.get("/api/v1/auth/me")).status_code == 200
    response = await client.post(
        "/api/v1/auth/password",
        json={
            "current_password": new_password,
            "new_password": new_password,
        },
    )
    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "password_unchanged"


@pytest.mark.parametrize("version", [True, -1, "0", None, 0.0])
async def test_invalid_token_version(
    profile_client: AsyncClient,
    profile_app: FastAPI,
    version: object,
) -> None:
    """Malformed version claims cannot bypass revocation."""
    settings = profile_app.state.settings.authentication
    secret = settings.jwt_secret_key.get_secret_value()
    token = profile_client.headers["Authorization"].removeprefix("Bearer ")
    claims = jwt.decode(token, secret, algorithms=[settings.algorithm])
    claims["ver"] = version
    token = jwt.encode(claims, secret, algorithm=settings.algorithm)
    response = await profile_client.get(
        "/api/v1/auth/me",
        headers={
            "Authorization": f"Bearer {token}",
        },
    )
    assert response.status_code == 401


def test_settings_migration(profile_db: Path) -> None:
    """An existing account survives upgrade with no language override."""
    config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    command.downgrade(config, "0002")
    with closing(sqlite3.connect(profile_db)) as connection:
        connection.execute(
            "INSERT INTO users (username, password) VALUES ('old', 'hash')"
        )
        connection.commit()
    command.upgrade(config, "head")
    with closing(sqlite3.connect(profile_db)) as connection:
        assert connection.execute(
            "SELECT username, password, preferred_locale, auth_version FROM users"
        ).fetchone() == ("old", "hash", None, 0)


async def test_swagger_authentication(profile_app: FastAPI) -> None:
    """Swagger uses the same credential endpoint as the SPA."""
    schema = profile_app.openapi()
    flow = schema["components"]["securitySchemes"]["OAuth2PasswordBearer"]
    assert flow["flows"]["password"]["tokenUrl"] == "/api/v1/auth/token"
    for path in ["/api/v1/auth/me", "/api/v1/auth/password"]:
        for operation in schema["paths"][path].values():
            assert operation["security"] == [{"OAuth2PasswordBearer": []}]

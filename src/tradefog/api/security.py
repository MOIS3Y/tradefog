"""Password hashing and signed access-token helpers."""

from datetime import UTC, datetime, timedelta
from typing import Literal
from uuid import uuid4

import jwt
from jwt.exceptions import InvalidTokenError
from pwdlib import PasswordHash
from pwdlib.exceptions import UnknownHashError

from tradefog.config.authentication import AuthenticationSettings

TokenKind = Literal["access", "refresh"]
PASSWORD_HASHER = PasswordHash.recommended()
DUMMY_PASSWORD_HASH = PASSWORD_HASHER.hash("unused-login-timing-placeholder")


def hash_password(password: str) -> str:
    """Create an Argon2 password hash suitable for the users table."""
    return PASSWORD_HASHER.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    """Verify a plaintext password against a stored Argon2 hash."""
    try:
        return PASSWORD_HASHER.verify(password, password_hash)
    except UnknownHashError:
        return False


def create_token(
    subject: int,
    kind: TokenKind,
    settings: AuthenticationSettings,
    auth_version: int = 0,
) -> str:
    """Issue a short-lived signed JWT with an explicit token purpose."""
    now = datetime.now(UTC)
    lifetime = (
        timedelta(minutes=settings.access_token_expire_minutes)
        if kind == "access"
        else timedelta(days=settings.refresh_token_expire_days)
    )
    claims = {
        "sub": str(subject),
        "type": kind,
        "iat": now,
        "exp": now + lifetime,
        "jti": str(uuid4()),
        "ver": auth_version,
    }
    return jwt.encode(
        claims,
        settings.jwt_secret_key.get_secret_value(),
        algorithm=settings.algorithm,
    )


def decode_token(
    token: str,
    expected_kind: TokenKind,
    settings: AuthenticationSettings,
) -> tuple[int, int] | None:
    """Return subject and credential version for a valid token purpose."""
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key.get_secret_value(),
            algorithms=[settings.algorithm],
            options={"require": ["sub", "type", "iat", "exp", "jti"]},
        )
        if payload.get("type") != expected_kind:
            return None
        subject = payload.get("sub")
        if not isinstance(subject, str) or not subject.isascii():
            return None
        if not subject.isdecimal() or len(subject) > 19:
            return None
        identifier = int(subject)
        version = payload.get("ver", 0)
        if type(version) is not int or version < 0:
            return None
        return (identifier, version) if 0 < identifier <= 2**63 - 1 else None
    except (InvalidTokenError, ValueError, TypeError):
        return None

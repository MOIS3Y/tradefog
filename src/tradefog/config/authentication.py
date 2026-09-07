"""Authentication and token configuration."""

from typing import Literal

from pydantic import Field, SecretStr

from tradefog.config.base import ConfigSection


class AuthenticationSettings(ConfigSection):
    """JWT and token authentication settings."""

    jwt_secret_key: SecretStr = SecretStr(
        "development-only-jwt-secret-change-before-production-2026"
    )
    algorithm: Literal["HS256", "HS384", "HS512"] = "HS256"
    access_token_expire_minutes: int = Field(default=15, gt=0)
    refresh_token_expire_days: int = Field(default=7, gt=0)

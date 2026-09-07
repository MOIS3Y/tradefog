"""Authentication and token configuration."""

from pydantic import SecretStr

from tradefog.config.base import ConfigSection


class AuthenticationSettings(ConfigSection):
    """JWT and token authentication settings."""

    jwt_secret_key: SecretStr = SecretStr("insecure-jwt-secret-key-tradefog")
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 7

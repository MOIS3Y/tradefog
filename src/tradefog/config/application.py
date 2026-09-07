"""Application and general API configuration."""

from pydantic import Field, SecretStr, field_validator

from tradefog.config.base import ConfigSection


class ApplicationSettings(ConfigSection):
    """Settings that control the FastAPI application runtime mode."""

    app_name: str = "Tradefog"
    api_prefix: str = "/api/v1"
    debug: bool = False
    secret_key: SecretStr = SecretStr(
        "insecure-development-secret-key-tradefog"
    )
    cors_origins: list[str] = Field(
        default_factory=lambda: [
            "http://localhost:3000",
            "http://localhost:5173",
            "http://127.0.0.1:8000",
        ]
    )

    @field_validator("secret_key")
    @classmethod
    def reject_required_placeholder(cls, secret_key: SecretStr) -> SecretStr:
        """Reject the marker used by example configuration files."""
        del cls
        if secret_key.get_secret_value() == "!required":
            raise ValueError("application.secret_key must be configured")
        return secret_key

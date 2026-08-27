"""Application and security-related configuration."""

from pydantic import Field, SecretStr, field_validator

from tradefog.config.base import ConfigSection


class ApplicationSettings(ConfigSection):
    """Settings that control the Django application's runtime mode."""

    secret_key: SecretStr = SecretStr("django-insecure-development-only")
    debug: bool = False
    allowed_hosts: list[str] = Field(default_factory=list)

    @field_validator("secret_key")
    @classmethod
    def reject_required_placeholder(cls, secret_key: SecretStr) -> SecretStr:
        """Reject the marker used by example configuration files."""
        del cls
        if secret_key.get_secret_value() == "!required":
            raise ValueError("application.secret_key must be configured")
        return secret_key

    def django_secret_key(self) -> str:
        """Return the secret key in the representation Django expects."""
        return self.secret_key.get_secret_value()

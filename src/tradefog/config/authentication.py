"""Django authentication configuration."""

from tradefog.config.base import ConfigSection


class AuthenticationSettings(ConfigSection):
    """Provide fixed Django authentication settings."""

    def user_model(self) -> str:
        """Return the configured application user model."""
        return "accounts.User"

    def login_url(self) -> str:
        """Return the named login route."""
        return "accounts:login"

    def login_redirect_url(self) -> str:
        """Return the route used after a successful login."""
        return "journal:home"

    def logout_redirect_url(self) -> str:
        """Return the route used after logout."""
        return "accounts:login"

    def password_validators(self) -> list[dict[str, str]]:
        """Return the enabled Django password validators."""
        validator_prefix = "django.contrib.auth.password_validation"
        return [
            {
                "NAME": (
                    f"{validator_prefix}.UserAttributeSimilarityValidator"
                ),
            },
            {
                "NAME": f"{validator_prefix}.MinimumLengthValidator",
            },
            {
                "NAME": f"{validator_prefix}.CommonPasswordValidator",
            },
            {
                "NAME": f"{validator_prefix}.NumericPasswordValidator",
            },
        ]

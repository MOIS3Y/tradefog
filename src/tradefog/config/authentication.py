"""Django authentication configuration."""

from tradefog.config.base import ConfigSection


class AuthenticationSettings(ConfigSection):
    """Provide fixed Django authentication settings."""

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

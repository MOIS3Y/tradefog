"""Logging-related runtime configuration."""

from typing import Literal

from pydantic import field_validator

from tradefog.config.base import ConfigSection

LogLevel = Literal[
    "DEBUG",
    "INFO",
    "WARNING",
    "ERROR",
    "CRITICAL",
]


class LoggingSettings(ConfigSection):
    """Configure consistent application and framework console logging."""

    level: LogLevel = "INFO"

    @field_validator("level", mode="before")
    @classmethod
    def normalize_level(cls, level: object) -> object:
        """Accept conventional logging levels case-insensitively."""
        if isinstance(level, str):
            return level.upper()
        return level

    def django_logging(self) -> dict[str, object]:
        """Return Django's standard dictConfig logging configuration."""
        return {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                "console": {
                    "()": "tradefog.logging.UtcFormatter",
                    "format": (
                        "%(asctime)s %(levelname)s %(name)s: %(message)s"
                    ),
                    "datefmt": "%Y-%m-%dT%H:%M:%SZ",
                },
            },
            "handlers": {
                "console": {
                    "class": "logging.StreamHandler",
                    "formatter": "console",
                    "stream": "ext://sys.stdout",
                },
            },
            "root": {
                "handlers": ["console"],
                "level": self.level,
            },
            "loggers": {
                logger_name: {
                    "handlers": ["console"],
                    "level": self.level,
                    "propagate": False,
                }
                for logger_name in (
                    "django",
                    "django.server",
                    "tradefog",
                    "uvicorn",
                )
            },
        }

"""Logging-related runtime configuration."""

from typing import Literal

from pydantic import field_validator

from tradefog.config.base import ConfigSection

LogLevel = Literal[
    "TRACE",
    "DEBUG",
    "INFO",
    "SUCCESS",
    "WARNING",
    "ERROR",
    "CRITICAL",
]


class LoggingSettings(ConfigSection):
    """Configure Loguru logging parameters."""

    level: LogLevel = "INFO"
    diagnose: bool = False
    backtrace: bool = True

    @field_validator("level", mode="before")
    @classmethod
    def normalize_level(cls, level: object) -> object:
        """Accept conventional logging levels case-insensitively."""
        if isinstance(level, str):
            return level.upper()
        return level

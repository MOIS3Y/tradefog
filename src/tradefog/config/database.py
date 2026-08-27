"""Database-related runtime settings."""

from pathlib import Path
from typing import Literal

from platformdirs import user_data_path
from pydantic import Field, SecretStr, field_validator

from tradefog.config.base import (
    ConfigSection,
    resolve_config_relative_path,
)


def default_database_path() -> Path:
    """Return the XDG-derived default path for the SQLite database."""
    return (
        user_data_path(
            appname="tradefog",
            appauthor=False,
        )
        / "db.sqlite3"
    )


class SQLiteSettings(ConfigSection):
    """SQLite-specific settings."""

    path: Path = Field(default_factory=default_database_path)

    @field_validator("path")
    @classmethod
    def resolve_path(cls, path: Path) -> Path:
        """Resolve relative database paths from the configuration file."""
        del cls
        return resolve_config_relative_path(path)


class PostgreSQLSettings(ConfigSection):
    """PostgreSQL-specific settings."""

    name: str = "tradefog"
    user: str = "tradefog"
    password: SecretStr = SecretStr("")
    host: str = "localhost"
    port: int = 5432


class DatabaseSettings(ConfigSection):
    """Select and configure the active database backend."""

    active: Literal["sqlite", "psql"] = "sqlite"
    sqlite: SQLiteSettings = Field(default_factory=SQLiteSettings)
    psql: PostgreSQLSettings = Field(default_factory=PostgreSQLSettings)

    def django_databases(self) -> dict[str, dict[str, object]]:
        """Translate the selected backend into Django's database mapping."""
        default: dict[str, object]
        if self.active == "sqlite":
            default = {
                "ENGINE": "django.db.backends.sqlite3",
                "NAME": self.sqlite.path,
            }
        else:
            default = {
                "ENGINE": "django.db.backends.postgresql",
                "NAME": self.psql.name,
                "USER": self.psql.user,
                "PASSWORD": self.psql.password.get_secret_value(),
                "HOST": self.psql.host,
                "PORT": self.psql.port,
            }

        return {
            "default": default,
        }

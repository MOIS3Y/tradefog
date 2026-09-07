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
        / "tradefog.db"
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

    @property
    def url(self) -> str:
        """Return standard database connection URL."""
        if self.active == "sqlite":
            return f"sqlite:///{self.sqlite.path.as_posix()}"
        pwd = self.psql.password.get_secret_value()
        auth = f"{self.psql.user}:{pwd}@" if pwd else f"{self.psql.user}@"
        return f"postgresql://{auth}{self.psql.host}:{self.psql.port}/{self.psql.name}"

    @property
    def async_url(self) -> str:
        """Return async database connection URL for SQLAlchemy/Alembic."""
        if self.active == "sqlite":
            return f"sqlite+aiosqlite:///{self.sqlite.path.as_posix()}"
        pwd = self.psql.password.get_secret_value()
        auth = f"{self.psql.user}:{pwd}@" if pwd else f"{self.psql.user}@"
        return f"postgresql+asyncpg://{auth}{self.psql.host}:{self.psql.port}/{self.psql.name}"

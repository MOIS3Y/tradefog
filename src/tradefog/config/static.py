"""Static-file configuration."""

from pathlib import Path

from platformdirs import user_cache_path
from pydantic import Field, field_validator

from tradefog.config.base import (
    BASE_DIR,
    ConfigSection,
    resolve_config_relative_path,
)


def default_static_root() -> Path:
    """Return the XDG-derived cache directory for collected static files."""
    return (
        user_cache_path(
            appname="tradefog",
            appauthor=False,
        )
        / "static"
    )


class StaticSettings(ConfigSection):
    """Configure collected static files and their public URL."""

    url: str = "/static/"
    root: Path = Field(default_factory=default_static_root)

    @field_validator("root")
    @classmethod
    def resolve_root(cls, root: Path) -> Path:
        """Resolve relative static roots from the configuration file."""
        del cls
        return resolve_config_relative_path(root)

    def mount_path(self) -> str:
        """Return the URL path expected by Starlette's static mount."""
        return f"/{self.url.strip('/')}"

    def source_dirs(self) -> list[Path]:
        """Return package directories containing source static files."""
        return [BASE_DIR / "static"]

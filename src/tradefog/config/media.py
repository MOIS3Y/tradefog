"""User-uploaded media configuration."""

from pathlib import Path

from platformdirs import user_data_path
from pydantic import Field, field_validator

from tradefog.config.base import (
    ConfigSection,
    resolve_config_relative_path,
)


def default_media_root() -> Path:
    """Return the XDG-derived directory for uploaded media."""
    return (
        user_data_path(
            appname="tradefog",
            appauthor=False,
        )
        / "media"
    )


class MediaSettings(ConfigSection):
    """Configure user-uploaded files and their public URL."""

    url: str = "/media/"
    root: Path = Field(default_factory=default_media_root)

    @field_validator("root")
    @classmethod
    def resolve_root(cls, root: Path) -> Path:
        """Resolve relative media roots from the configuration file."""
        del cls
        return resolve_config_relative_path(root)

    def mount_path(self) -> str:
        """Return the URL path expected by Starlette's media mount."""
        return f"/{self.url.strip('/')}"

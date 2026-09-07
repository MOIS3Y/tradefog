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
    """Configure private user-uploaded file storage."""

    root: Path = Field(default_factory=default_media_root)
    max_attachment_size_mib: int = Field(default=10, ge=0)

    @field_validator("root")
    @classmethod
    def resolve_root(cls, root: Path) -> Path:
        """Resolve relative media roots from the configuration file."""
        del cls
        return resolve_config_relative_path(root)

    def max_attachment_size_bytes(self) -> int | None:
        """Return the attachment limit in bytes, or no limit for zero."""
        if self.max_attachment_size_mib == 0:
            return None
        return self.max_attachment_size_mib * 1024 * 1024

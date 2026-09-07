"""Configuration for optionally serving the compiled frontend."""

from pathlib import Path

from pydantic import field_validator

from tradefog.config.base import ConfigSection, resolve_config_relative_path


class FrontendSettings(ConfigSection):
    """Identify the optional directory containing the compiled SPA."""

    path: Path | None = None

    @field_validator("path")
    @classmethod
    def resolve_path(cls, path: Path | None) -> Path | None:
        """Resolve a configured frontend path relative to its TOML file."""
        del cls
        return resolve_config_relative_path(path) if path is not None else None

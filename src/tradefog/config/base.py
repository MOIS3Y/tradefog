"""Shared behavior for runtime configuration models."""

import os
from pathlib import Path
from typing import ClassVar, override

from platformdirs import user_config_path
from pydantic import BaseModel, ConfigDict
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
    TomlConfigSettingsSource,
)

CONFIG_PATH_ENV = "TRADEFOG_CONFIG"
BASE_DIR = Path(__file__).resolve().parent.parent


def config_file_path() -> Path:
    """Return the explicit or XDG-derived configuration file path."""
    configured_path = os.environ.get(CONFIG_PATH_ENV)
    if configured_path:
        return Path(configured_path).expanduser()

    return (
        user_config_path(
            appname="tradefog",
            appauthor=False,
        )
        / "settings.toml"
    )


def resolve_config_relative_path(path: Path) -> Path:
    """Resolve a configured path relative to its TOML file."""
    expanded_path = Path(os.path.expandvars(path)).expanduser()
    if expanded_path.is_absolute():
        return expanded_path
    return (config_file_path().parent / expanded_path).resolve()


class ConfigSection(BaseModel):
    """Base model for an immutable thematic configuration section."""

    model_config: ClassVar[ConfigDict] = ConfigDict(
        extra="forbid",
        frozen=True,
    )


class TradefogSettings(BaseSettings):
    """Load environment values before the shared TOML configuration."""

    model_config: ClassVar[SettingsConfigDict] = SettingsConfigDict(
        case_sensitive=False,
        env_nested_delimiter="__",
        env_prefix="TRADEFOG_",
        extra="forbid",
        frozen=True,
        nested_model_default_partial_update=True,
    )

    @classmethod
    @override
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        """Define explicit values, environment, TOML, then defaults."""
        del cls, dotenv_settings, file_secret_settings
        return (
            init_settings,
            env_settings,
            TomlConfigSettingsSource(
                settings_cls,
                toml_file=config_file_path(),
            ),
        )

"""Root application configuration."""

from functools import lru_cache

from pydantic import Field

from tradefog.config.application import ApplicationSettings
from tradefog.config.authentication import AuthenticationSettings
from tradefog.config.base import TradefogSettings
from tradefog.config.database import DatabaseSettings
from tradefog.config.frontend import FrontendSettings
from tradefog.config.logging import LoggingSettings
from tradefog.config.media import MediaSettings
from tradefog.config.uvicorn import UvicornSettings


class Settings(TradefogSettings):
    """Complete tradefog runtime configuration."""

    application: ApplicationSettings = Field(
        default_factory=ApplicationSettings,
    )
    database: DatabaseSettings = Field(default_factory=DatabaseSettings)
    frontend: FrontendSettings = Field(default_factory=FrontendSettings)
    authentication: AuthenticationSettings = Field(
        default_factory=AuthenticationSettings,
    )
    logging: LoggingSettings = Field(default_factory=LoggingSettings)
    media: MediaSettings = Field(default_factory=MediaSettings)
    uvicorn: UvicornSettings = Field(default_factory=UvicornSettings)


@lru_cache
def get_settings() -> Settings:
    """Return cached runtime settings instance."""
    return Settings()

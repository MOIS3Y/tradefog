"""Root application configuration."""

from pydantic import Field

from tradefog.config.application import ApplicationSettings
from tradefog.config.authentication import AuthenticationSettings
from tradefog.config.base import TradefogSettings
from tradefog.config.database import DatabaseSettings
from tradefog.config.django import DjangoSettings
from tradefog.config.localization import LocalizationSettings
from tradefog.config.logging import LoggingSettings
from tradefog.config.media import MediaSettings
from tradefog.config.static import StaticSettings
from tradefog.config.templates import TemplateSettings
from tradefog.config.uvicorn import UvicornSettings


class Settings(TradefogSettings):
    """Complete tradefog runtime configuration."""

    application: ApplicationSettings = Field(
        default_factory=ApplicationSettings,
    )
    django: DjangoSettings = Field(default_factory=DjangoSettings)
    templates: TemplateSettings = Field(default_factory=TemplateSettings)
    database: DatabaseSettings = Field(default_factory=DatabaseSettings)
    authentication: AuthenticationSettings = Field(
        default_factory=AuthenticationSettings,
    )
    localization: LocalizationSettings = Field(
        default_factory=LocalizationSettings,
    )
    logging: LoggingSettings = Field(default_factory=LoggingSettings)
    static: StaticSettings = Field(default_factory=StaticSettings)
    media: MediaSettings = Field(default_factory=MediaSettings)
    uvicorn: UvicornSettings = Field(default_factory=UvicornSettings)

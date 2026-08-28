"""Django application configuration for the trading journal."""

from typing import final

from django.apps import AppConfig


@final
class JournalConfig(AppConfig):
    """Configure the tradefog journal application."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "tradefog.journal"

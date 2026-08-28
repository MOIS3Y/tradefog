"""Django application configuration for user accounts."""

from typing import final

from django.apps import AppConfig


@final
class AccountsConfig(AppConfig):
    """Configure the tradefog accounts application."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "tradefog.accounts"

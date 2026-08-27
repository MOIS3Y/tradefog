"""Django application configuration for the project CLI."""

from django.apps import AppConfig


class CliConfig(AppConfig):
    """Configure project-level management commands."""

    name: str = "tradefog.cli"

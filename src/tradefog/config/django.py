"""Fixed Django framework configuration."""

from tradefog.config.base import ConfigSection


class DjangoSettings(ConfigSection):
    """Provide structural settings that are not user-configurable."""

    def installed_apps(self) -> list[str]:
        """Return the enabled Django applications."""
        return [
            "django.contrib.admin",
            "django.contrib.auth",
            "django.contrib.contenttypes",
            "django.contrib.sessions",
            "django.contrib.messages",
            "django.contrib.staticfiles",
            "django_typer",
            "tradefog.accounts.apps.AccountsConfig",
            "tradefog.cli.apps.CliConfig",
        ]

    def middleware(self) -> list[str]:
        """Return the Django middleware chain."""
        return [
            "django.middleware.security.SecurityMiddleware",
            "django.contrib.sessions.middleware.SessionMiddleware",
            "django.middleware.locale.LocaleMiddleware",
            "django.middleware.common.CommonMiddleware",
            "django_htmx.middleware.HtmxMiddleware",
            "django.middleware.csrf.CsrfViewMiddleware",
            "django.contrib.auth.middleware.AuthenticationMiddleware",
            "django.contrib.messages.middleware.MessageMiddleware",
            "django.middleware.clickjacking.XFrameOptionsMiddleware",
        ]

    def root_urlconf(self) -> str:
        """Return the root URL configuration module."""
        return "tradefog.urls"

    def asgi_application(self) -> str:
        """Return the ASGI application import path."""
        return "tradefog.asgi.application"

    def default_auto_field(self) -> str:
        """Return the default model primary-key field type."""
        return "django.db.models.BigAutoField"

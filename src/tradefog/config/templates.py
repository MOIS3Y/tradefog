"""Django template-engine configuration."""

from tradefog.config.base import BASE_DIR, ConfigSection


class TemplateSettings(ConfigSection):
    """Provide the Django template backend configuration."""

    def django_templates(self) -> list[dict[str, object]]:
        """Return configured Django template backends."""
        return [
            {
                "BACKEND": "django.template.backends.django.DjangoTemplates",
                "DIRS": [BASE_DIR / "templates"],
                "APP_DIRS": True,
                "OPTIONS": {
                    "context_processors": [
                        "django.template.context_processors.request",
                        "django.contrib.auth.context_processors.auth",
                        "django.contrib.messages.context_processors.messages",
                    ],
                },
            },
        ]

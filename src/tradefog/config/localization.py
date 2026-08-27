"""Localization-related configuration."""

from pathlib import Path
from typing import Literal

from django.utils.translation import gettext_lazy

from tradefog.config.base import BASE_DIR, ConfigSection

LanguageCode = Literal["en", "ru"]


class LocalizationSettings(ConfigSection):
    """Settings that control language, time zone, and translation."""

    time_zone: str = "UTC"

    def language_code(self) -> LanguageCode:
        """Return the fixed source and fallback language."""
        return "en"

    def languages(self) -> list[tuple[str, object]]:
        """Return the languages shipped with the application."""
        return [
            ("en", gettext_lazy("English")),
            ("ru", gettext_lazy("Russian")),
        ]

    def locale_paths(self) -> list[Path]:
        """Return package-relative translation catalog locations."""
        return [BASE_DIR / "locale"]

    def use_i18n(self) -> bool:
        """Keep Django translation support enabled."""
        return True

    def use_tz(self) -> bool:
        """Keep timezone-aware datetime handling enabled."""
        return True

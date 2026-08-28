"""Django admin configuration for journal models."""

from typing import final

from django.contrib import admin

from tradefog.journal.models import ProfileInstrument, TradingProfile


@admin.register(TradingProfile)
@final
class TradingProfileAdmin(admin.ModelAdmin):  # pyright: ignore[reportMissingTypeArgument]
    """Expose trading profiles for administrative support."""

    list_display = (
        "name",
        "owner",
        "venue_name",
        "capital_currency",
        "archived_at",
    )
    list_filter = ("capital_currency", "archived_at")
    search_fields = ("name", "venue_name", "owner__username")


@admin.register(ProfileInstrument)
@final
class ProfileInstrumentAdmin(admin.ModelAdmin):  # pyright: ignore[reportMissingTypeArgument]
    """Expose profile instruments for administrative support."""

    list_display = (
        "symbol",
        "profile",
        "market_type",
        "archived_at",
    )
    list_filter = ("market_type", "archived_at")
    search_fields = (
        "base_asset",
        "display_name",
        "profile__capital_currency",
        "profile__name",
    )

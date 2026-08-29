"""Django admin configuration for journal models."""

from typing import final

from django.contrib import admin

from tradefog.journal.models import (
    CapitalOperation,
    ProfileInstrument,
    TradingProfile,
)


@admin.register(TradingProfile)
@final
class TradingProfileAdmin(admin.ModelAdmin):  # pyright: ignore[reportMissingTypeArgument]
    """Expose trading profiles for administrative support."""

    list_display = (
        "name",
        "owner",
        "provider",
        "capital_currency",
        "status",
    )
    list_filter = ("provider", "capital_currency", "status")
    search_fields = ("name", "owner__username")


@admin.register(CapitalOperation)
@final
class CapitalOperationAdmin(admin.ModelAdmin):  # pyright: ignore[reportMissingTypeArgument]
    """Expose explicit profile allocation changes for support."""

    list_display = (
        "profile",
        "operation_type",
        "amount",
        "created_at",
    )
    list_filter = ("operation_type",)
    search_fields = ("profile__name", "profile__owner__username", "note")


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

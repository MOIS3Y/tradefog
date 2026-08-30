"""Django admin configuration for journal models."""

from typing import final

from django.contrib import admin

from tradefog.journal.models import (
    Asset,
    CapitalOperation,
    ProfileTradingPair,
    Trade,
    TradeChecklist,
    TradingProfile,
)


@admin.register(Asset)
@final
class AssetAdmin(admin.ModelAdmin):  # pyright: ignore[reportMissingTypeArgument]
    """Expose owner-scoped asset identities for administrative support."""

    list_display = ("symbol", "name", "asset_class", "owner", "archived_at")
    list_filter = ("asset_class", "archived_at")
    search_fields = ("symbol", "name", "owner__username")


@admin.register(TradingProfile)
@final
class TradingProfileAdmin(admin.ModelAdmin):  # pyright: ignore[reportMissingTypeArgument]
    """Expose trading profiles for administrative support."""

    list_display = (
        "name",
        "owner",
        "provider",
        "capital_asset",
        "market_type",
        "status",
    )
    list_filter = ("provider", "market_type", "capital_asset", "status")
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


@admin.register(ProfileTradingPair)
@final
class ProfileTradingPairAdmin(admin.ModelAdmin):  # pyright: ignore[reportMissingTypeArgument]
    """Expose profile trading pairs for administrative support."""

    list_display = (
        "symbol",
        "profile",
        "asset",
        "archived_at",
    )
    list_filter = ("profile__market_type", "archived_at")
    search_fields = (
        "asset__symbol",
        "profile__capital_asset__symbol",
        "profile__name",
    )


@admin.register(Trade)
@final
class TradeAdmin(admin.ModelAdmin):  # pyright: ignore[reportMissingTypeArgument]
    """Expose journal decisions and their lifecycle state for support."""

    list_display = (
        "trading_pair",
        "profile",
        "direction",
        "status",
        "trade_date",
    )
    list_filter = ("status", "direction", "profile__market_type")
    search_fields = (
        "trading_pair__asset__symbol",
        "profile__name",
        "profile__owner__username",
    )


@admin.register(TradeChecklist)
@final
class TradeChecklistAdmin(
    admin.ModelAdmin  # pyright: ignore[reportMissingTypeArgument]
):
    """Expose immutable historical checklist answers for support."""

    list_display = ("trade", "schema_version", "updated_at")
    search_fields = (
        "trade__trading_pair__asset__symbol",
        "trade__profile__name",
        "trade__profile__owner__username",
    )

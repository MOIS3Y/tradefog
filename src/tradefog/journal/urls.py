"""URL configuration for the tradefog journal application."""

from django.urls import path

from tradefog.journal import views

app_name = "journal"

urlpatterns = [
    path("", views.home, name="home"),
    path("profiles/", views.profiles, name="profiles"),
    path("trades/", views.trades, name="trades"),
    path("trades/new/", views.trade_new, name="trade_new"),
    path("analytics/", views.analytics, name="analytics"),

    # Catalog:
    path(
        "catalog/assets/",
        views.asset_overview,
        name="asset_overview",
    ),
    path(
        "catalog/assets/create/",
        views.asset_create,
        name="asset_create",
    ),
    path(
        "catalog/assets/<int:pk>/delete/",
        views.asset_delete,
        name="asset_delete",
    ),
    path(
        "catalog/pairs/",
        views.pair_overview,
        name="pair_overview",
    ),
    path(
        "catalog/pairs/create/",
        views.pair_create,
        name="pair_create",
    ),
    path(
        "catalog/pairs/<int:pk>/delete/",
        views.pair_delete,
        name="pair_delete",
    ),
    path(
        "catalog/venues/",
        views.venue_overview,
        name="venue_overview",
    ),
    path(
        "catalog/venues/create/",
        views.venue_create,
        name="venue_create",
    ),
    path(
        "catalog/venues/<int:pk>/",
        views.venue_detail,
        name="venue_detail",
    ),
    path(
        "catalog/venues/<int:pk>/edit/",
        views.venue_edit,
        name="venue_edit",
    ),
    path(
        "catalog/venues/<int:pk>/delete/",
        views.venue_delete,
        name="venue_delete",
    ),
    path(
        "catalog/venues/<int:pk>/wallet-assets/add/",
        views.wallet_asset_add,
        name="wallet_asset_add",
    ),
    path(
        "catalog/venues/<int:pk>/wallet-assets/<int:asset_pk>/remove/",
        views.wallet_asset_remove,
        name="wallet_asset_remove",
    ),
    path(
        "catalog/venues/<int:pk>/instruments/add/",
        views.instrument_add,
        name="instrument_add",
    ),
    path(
        "catalog/venues/<int:pk>/instruments/<int:instrument_pk>/edit/",
        views.instrument_edit,
        name="instrument_edit",
    ),
    path(
        "catalog/venues/<int:pk>/instruments/<int:instrument_pk>/detail/",
        views.instrument_detail,
        name="instrument_detail",
    ),
    path(
        "catalog/venues/<int:pk>/instruments/<int:instrument_pk>/delete/",
        views.instrument_delete,
        name="instrument_delete",
    ),
]

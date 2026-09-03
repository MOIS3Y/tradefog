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
]

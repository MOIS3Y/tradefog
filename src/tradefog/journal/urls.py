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
    path("settings/", views.settings, name="settings"),
]
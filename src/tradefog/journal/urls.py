"""Language-prefixed routes for the trading journal."""

from django.urls import path

from tradefog.journal import views

urlpatterns = [
    path("profiles/", views.profile_overview, name="profile_overview"),
    path(
        "profiles/archived/",
        views.archived_profile_overview,
        name="archived_profile_overview",
    ),
    path("profiles/new/", views.profile_create, name="profile_create"),
    path(
        "profiles/<int:profile_id>/",
        views.profile_detail,
        name="profile_detail",
    ),
    path(
        "profiles/<int:profile_id>/edit/",
        views.profile_edit,
        name="profile_edit",
    ),
    path(
        "profiles/<int:profile_id>/archive/",
        views.profile_archive,
        name="profile_archive",
    ),
    path(
        "profiles/<int:profile_id>/restore/",
        views.profile_restore,
        name="profile_restore",
    ),
    path(
        "profiles/<int:profile_id>/instruments/new/",
        views.instrument_create,
        name="instrument_create",
    ),
    path(
        "profiles/<int:profile_id>/instruments/<int:instrument_id>/edit/",
        views.instrument_edit,
        name="instrument_edit",
    ),
    path(
        "profiles/<int:profile_id>/instruments/<int:instrument_id>/archive/",
        views.instrument_archive,
        name="instrument_archive",
    ),
    path(
        "profiles/<int:profile_id>/instruments/<int:instrument_id>/restore/",
        views.instrument_restore,
        name="instrument_restore",
    ),
]

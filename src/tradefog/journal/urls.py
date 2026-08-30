"""Language-prefixed routes for the trading journal."""

from django.urls import path

from tradefog.journal import views

urlpatterns = [
    path("analytics/", views.analytics_overview, name="analytics_overview"),
    path("assets/", views.asset_overview, name="asset_overview"),
    path("assets/new/", views.asset_create, name="asset_create"),
    path(
        "assets/<int:asset_id>/edit/",
        views.asset_edit,
        name="asset_edit",
    ),
    path(
        "assets/<int:asset_id>/archive/",
        views.asset_archive,
        name="asset_archive",
    ),
    path(
        "assets/<int:asset_id>/restore/",
        views.asset_restore,
        name="asset_restore",
    ),
    path("trades/", views.trade_overview, name="trade_overview"),
    path(
        "trades/new/",
        views.trade_profile_select,
        name="trade_profile_select",
    ),
    path(
        "trades/new/<int:profile_id>/",
        views.trade_create,
        name="trade_create",
    ),
    path(
        "trades/new/<int:profile_id>/plan/",
        views.new_trade_plan,
        name="new_trade_plan",
    ),
    path("trades/<int:trade_id>/", views.trade_detail, name="trade_detail"),
    path(
        "trades/<int:trade_id>/plan/",
        views.trade_plan,
        name="trade_plan",
    ),
    path(
        "trades/<int:trade_id>/submit/",
        views.trade_submit,
        name="trade_submit",
    ),
    path(
        "trades/<int:trade_id>/open/",
        views.trade_open,
        name="trade_open",
    ),
    path(
        "trades/<int:trade_id>/cancel/",
        views.trade_cancel,
        name="trade_cancel",
    ),
    path(
        "trades/<int:trade_id>/close/",
        views.trade_close,
        name="trade_close",
    ),
    path(
        "trades/<int:trade_id>/date/",
        views.trade_date_edit,
        name="trade_date_edit",
    ),
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
        "profiles/<int:profile_id>/capital/deposit/",
        views.capital_deposit,
        name="capital_deposit",
    ),
    path(
        "profiles/<int:profile_id>/capital/withdraw/",
        views.capital_withdraw,
        name="capital_withdraw",
    ),
    path(
        "profiles/<int:profile_id>/capital/<int:operation_id>/edit/",
        views.capital_operation_edit,
        name="capital_operation_edit",
    ),
    path(
        "profiles/<int:profile_id>/capital/<int:operation_id>/delete/",
        views.capital_operation_delete,
        name="capital_operation_delete",
    ),
    path(
        "profiles/<int:profile_id>/pairs/new/",
        views.trading_pair_create,
        name="trading_pair_create",
    ),
    path(
        "profiles/<int:profile_id>/pairs/<int:pair_id>/edit/",
        views.trading_pair_edit,
        name="trading_pair_edit",
    ),
    path(
        "profiles/<int:profile_id>/pairs/<int:pair_id>/archive/",
        views.trading_pair_archive,
        name="trading_pair_archive",
    ),
    path(
        "profiles/<int:profile_id>/pairs/<int:pair_id>/restore/",
        views.trading_pair_restore,
        name="trading_pair_restore",
    ),
]

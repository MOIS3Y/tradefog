"""View functions grouped by domain.

The package replaces the former flat ``views`` module so every domain keeps
its request handling and rendering helpers together. URL configuration
imports the top-level package and relies on these re-exports.
"""

from tradefog.journal.views.catalog import (
    asset_create,
    asset_delete,
    asset_overview,
    instrument_add,
    instrument_delete,
    instrument_detail,
    instrument_edit,
    pair_create,
    pair_delete,
    pair_overview,
    venue_create,
    venue_delete,
    venue_detail,
    venue_edit,
    venue_overview,
    wallet_asset_add,
    wallet_asset_remove,
)
from tradefog.journal.views.profiles import (
    profile_archive,
    profile_create,
    profile_delete,
    profile_overview,
    profile_restore,
)
from tradefog.journal.views.shell import (
    analytics,
    home,
    trade_new,
    trades,
)

__all__ = [
    "analytics",
    "asset_create",
    "asset_delete",
    "asset_overview",
    "home",
    "instrument_add",
    "instrument_delete",
    "instrument_detail",
    "instrument_edit",
    "pair_create",
    "pair_delete",
    "pair_overview",
    "profile_archive",
    "profile_create",
    "profile_delete",
    "profile_overview",
    "profile_restore",
    "trade_new",
    "trades",
    "venue_create",
    "venue_delete",
    "venue_detail",
    "venue_edit",
    "venue_overview",
    "wallet_asset_add",
    "wallet_asset_remove",
]
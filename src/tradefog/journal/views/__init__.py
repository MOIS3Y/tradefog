"""View functions grouped by domain.

The package replaces the former flat ``views`` module so every domain keeps
its request handling and rendering helpers together. URL configuration
imports the top-level package and relies on these re-exports.
"""

from tradefog.journal.views.catalog import (
    asset_create,
    asset_delete,
    asset_overview,
    pair_create,
    pair_delete,
    pair_overview,
)
from tradefog.journal.views.shell import (
    analytics,
    home,
    profiles,
    trade_new,
    trades,
)

__all__ = [
    "analytics",
    "asset_create",
    "asset_delete",
    "asset_overview",
    "home",
    "pair_create",
    "pair_delete",
    "pair_overview",
    "profiles",
    "trade_new",
    "trades",
]
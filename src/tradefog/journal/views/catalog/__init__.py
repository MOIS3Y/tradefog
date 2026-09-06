"""Views for the shared, staff-managed reference catalog.

The package is split by domain so the growing catalog stays maintainable:
:mod:`assets` owns the asset collection, :mod:`pairs` owns the trading pairs
collection, :mod:`venues` owns the venue collection, detail page, and wallet
assets, and :mod:`instruments` owns venue instruments. :mod:`common` holds the
shared list helpers. URL configuration imports the top-level ``views`` package,
which re-exports the catalog views.
"""

from tradefog.journal.views.catalog.assets import (
    asset_create,
    asset_delete,
    asset_overview,
)
from tradefog.journal.views.catalog.instruments import (
    instrument_add,
    instrument_delete,
    instrument_detail,
    instrument_edit,
)
from tradefog.journal.views.catalog.pairs import (
    pair_create,
    pair_delete,
    pair_overview,
)
from tradefog.journal.views.catalog.venues import (
    venue_archive,
    venue_create,
    venue_delete,
    venue_detail,
    venue_edit,
    venue_overview,
    venue_restore,
    wallet_asset_add,
    wallet_asset_edit,
    wallet_asset_remove,
)

__all__ = [
    "asset_create",
    "asset_delete",
    "asset_overview",
    "instrument_add",
    "instrument_delete",
    "instrument_detail",
    "instrument_edit",
    "pair_create",
    "pair_delete",
    "pair_overview",
    "venue_archive",
    "venue_create",
    "venue_delete",
    "venue_detail",
    "venue_edit",
    "venue_overview",
    "venue_restore",
    "wallet_asset_add",
    "wallet_asset_edit",
    "wallet_asset_remove",
]

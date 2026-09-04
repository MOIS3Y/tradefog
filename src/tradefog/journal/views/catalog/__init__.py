"""Views for the shared, staff-managed reference catalog.

The package is split by domain so the growing catalog stays maintainable:
:mod:`assets` owns the asset collection and :mod:`pairs` owns the trading
pairs collection, while :mod:`common` holds the shared list helpers. URL
configuration imports the top-level ``views`` package, which re-exports the
catalog views.
"""

from tradefog.journal.views.catalog.assets import (
    asset_create,
    asset_delete,
    asset_overview,
)
from tradefog.journal.views.catalog.pairs import (
    pair_create,
    pair_delete,
    pair_overview,
)

__all__ = [
    "asset_create",
    "asset_delete",
    "asset_overview",
    "pair_create",
    "pair_delete",
    "pair_overview",
]
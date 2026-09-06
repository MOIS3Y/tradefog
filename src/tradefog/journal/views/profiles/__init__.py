"""Views for owner-scoped trading profiles.

The package groups profile overview (card grid), profile detail (tabs),
wallet management, and strategy views. URL configuration imports the
top-level views package which re-exports from here.
"""

from tradefog.journal.views.profiles.detail import (
    profile_detail,
    profile_edit,
)
from tradefog.journal.views.profiles.overview import (
    profile_archive,
    profile_create,
    profile_delete,
    profile_overview,
    profile_restore,
)
from tradefog.journal.views.profiles.strategies import (
    strategies_context,
    strategy_archive,
    strategy_capital_add,
    strategy_capital_archive,
    strategy_capital_restore,
    strategy_create,
    strategy_detail,
    strategy_edit,
    strategy_restore,
)
from tradefog.journal.views.profiles.wallet import (
    wallet_add,
    wallet_deposit,
    wallet_edit,
    wallet_operation_edit,
    wallet_remove,
    wallet_restore,
    wallet_withdraw,
)

__all__ = [
    "profile_archive",
    "profile_create",
    "profile_delete",
    "profile_detail",
    "profile_edit",
    "profile_overview",
    "profile_restore",
    "strategies_context",
    "strategy_archive",
    "strategy_capital_add",
    "strategy_capital_archive",
    "strategy_capital_restore",
    "strategy_create",
    "strategy_detail",
    "strategy_edit",
    "strategy_restore",
    "wallet_add",
    "wallet_deposit",
    "wallet_edit",
    "wallet_operation_edit",
    "wallet_remove",
    "wallet_restore",
    "wallet_withdraw",
]

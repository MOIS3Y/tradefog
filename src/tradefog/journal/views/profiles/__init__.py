"""Views for owner-scoped trading profiles.

The package groups profile overview (card grid), profile detail (tabs),
wallet management, and strategy views. URL configuration imports the
top-level views package which re-exports from here.
"""

from tradefog.journal.views.profiles.detail import profile_detail
from tradefog.journal.views.profiles.overview import (
    profile_archive,
    profile_create,
    profile_delete,
    profile_overview,
    profile_restore,
)

__all__ = [
    "profile_archive",
    "profile_create",
    "profile_delete",
    "profile_detail",
    "profile_overview",
    "profile_restore",
]

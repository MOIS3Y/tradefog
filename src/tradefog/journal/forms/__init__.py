"""Form package grouped by domain.

Re-exports every form so views keep stable imports from
``tradefog.journal.forms`` regardless of which module owns a form.
"""

from tradefog.journal.forms.catalog import (
    AssetForm,
    TradingPairForm,
    VenueForm,
    VenueInstrumentForm,
    VenueWalletAssetForm,
)
from tradefog.journal.forms.profiles import TradingProfileForm

__all__ = [
    "AssetForm",
    "TradingPairForm",
    "TradingProfileForm",
    "VenueForm",
    "VenueInstrumentForm",
    "VenueWalletAssetForm",
]
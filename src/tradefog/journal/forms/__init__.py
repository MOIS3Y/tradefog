"""Form package grouped by domain.

Re-exports every form so views keep stable imports from
``tradefog.journal.forms`` regardless of which module owns a form.
"""

from tradefog.journal.forms.catalog import (
    AssetForm,
    TradingPairForm,
    VenueForm,
    VenueInstrumentForm,
    VenueSettingsForm,
    VenueWalletAssetEditForm,
    VenueWalletAssetForm,
)
from tradefog.journal.forms.profiles import (
    TradingProfileForm,
    TradingProfileSettingsForm,
)
from tradefog.journal.forms.strategies import (
    StrategyCapitalForm,
    TradingStrategyForm,
)
from tradefog.journal.forms.wallet import (
    WalletAssetAddForm,
    WalletAssetEditForm,
    WalletOperationForm,
    WalletOperationNoteForm,
)

__all__ = [
    "AssetForm",
    "StrategyCapitalForm",
    "TradingPairForm",
    "TradingProfileForm",
    "TradingProfileSettingsForm",
    "TradingStrategyForm",
    "VenueForm",
    "VenueInstrumentForm",
    "VenueSettingsForm",
    "VenueWalletAssetEditForm",
    "VenueWalletAssetForm",
    "WalletAssetAddForm",
    "WalletAssetEditForm",
    "WalletOperationForm",
    "WalletOperationNoteForm",
]

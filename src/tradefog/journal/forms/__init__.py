"""Form package grouped by domain.

Re-exports every form so views keep stable imports from
``tradefog.journal.forms`` regardless of which module owns a form.
"""

from tradefog.journal.forms.catalog import AssetForm, TradingPairForm

__all__ = ["AssetForm", "TradingPairForm"]
"""Views for trade workspace, position planning, review, and lifecycle."""

from tradefog.journal.views.trades.attachments import (
    trade_attachment_delete,
    trade_attachment_serve,
    trade_attachment_upload,
)
from tradefog.journal.views.trades.checklist import trade_checklist_preview
from tradefog.journal.views.trades.lifecycle import (
    trade_cancel_action,
    trade_close_action,
    trade_open_action,
    trade_submit,
)
from tradefog.journal.views.trades.market import trade_market_preview
from tradefog.journal.views.trades.overview import (
    trade_delete,
    trade_overview,
)
from tradefog.journal.views.trades.plan import trade_plan_preview
from tradefog.journal.views.trades.review import (
    trade_description_update,
    trade_review_toggle,
)
from tradefog.journal.views.trades.workspace import (
    trade_create,
    trade_options,
    trade_workspace,
)

__all__ = [
    "trade_attachment_delete",
    "trade_attachment_serve",
    "trade_attachment_upload",
    "trade_cancel_action",
    "trade_checklist_preview",
    "trade_close_action",
    "trade_create",
    "trade_delete",
    "trade_description_update",
    "trade_market_preview",
    "trade_open_action",
    "trade_options",
    "trade_overview",
    "trade_plan_preview",
    "trade_review_toggle",
    "trade_submit",
    "trade_workspace",
]

from tradefog.journal.views.trades.attachments import (
    trade_attachment_delete,
    trade_attachment_serve,
    trade_attachment_upload,
)
from tradefog.journal.views.trades.lifecycle import (
    trade_cancel_action,
    trade_close_action,
    trade_open_action,
    trade_submit,
)
from tradefog.journal.views.trades.overview import (
    trade_delete,
    trade_overview,
)
from tradefog.journal.views.trades.review import (
    trade_description_update,
    trade_review_toggle,
)
from tradefog.journal.views.trades.workspace import (
    trade_create,
    trade_market_data,
    trade_workspace,
    trade_workspace_options,
)

__all__ = [
    "trade_attachment_delete",
    "trade_attachment_serve",
    "trade_attachment_upload",
    "trade_cancel_action",
    "trade_close_action",
    "trade_create",
    "trade_delete",
    "trade_description_update",
    "trade_market_data",
    "trade_open_action",
    "trade_overview",
    "trade_review_toggle",
    "trade_submit",
    "trade_workspace",
    "trade_workspace_options",
]

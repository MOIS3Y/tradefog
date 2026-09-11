"""Shared API guidance and coherent examples, separate from handlers."""

from pydantic import JsonValue

API_DESCRIPTION = """
Tradefog is a personal trading journal. Wallet operations and trade lifecycle
actions record journal facts; they do not transfer funds or place exchange
orders.

### Authentication and ownership

Use **Authorize** with your username and password; leave client credentials
empty. Business endpoints, including public market data, require a bearer
access token. Accounts are provisioned through the installation's CLI.
Journal resources belong to the authenticated user's profiles. Missing and
inaccessible journal resources return 404.

### Values and partial updates

Send financial values as decimal strings, such as `"1000.00"` or `"0.001"`,
to preserve precision. Decimal response values are strings. Percentages use
percentage points: `"1.50"` means 1.5%, not 150%. Amounts are denominated in
the referenced asset; prices use the instrument's quote asset.

For metadata PATCH requests, omitted fields retain their values. Explicit `null`
clears a field only where that operation allows it; it does not mean
"leave unchanged". The wallet-operation note PATCH replaces the note: an
omitted or null note clears it. Examples are illustrative, not defaults or
live data.

### Collections

Journal pages contain `items`, the filtered `total`, `page` (starting at 1),
and `page_size` (default 25, maximum 100). An out-of-range page is empty.
Use the filters exposed by each operation. Sort keys are endpoint-specific;
unsupported keys return 422. Market collections use provider cursors instead.

### Errors

Application errors normally have
`{"detail": {"code": "conflict", "message": "..."}}`.
Use the code for client decisions and the message for explanation.
401 requires authentication; 404 means the resource is unavailable to you;
409 means the requested action conflicts with current journal state.
422 may be an application error or a validation response whose `detail` is
an array of field errors. Authentication middleware can also return a string
`detail`. Market failures may include `Retry-After` in seconds; respect that
delay before retrying. Re-read journal state before retrying a mutation after
an uncertain network outcome.
"""

ASSET_EXAMPLE: dict[str, JsonValue] = {
    "id": 1,
    "profile_id": 1,
    "symbol": "USDT",
    "name": "Tether",
    "asset_type": "crypto",
    "is_archived": False,
    "risk_stop_capital": "500.00",
    "status": "active",
    "balance": "1000.00",
    "allocated": "400.00",
    "reserved": "100.00",
    "available": "900.00",
    "uncommitted": "600.00",
}

WALLET_OPERATION_EXAMPLE: dict[str, JsonValue] = {
    "kind": "withdrawal",
    "amount": "100.00",
    "note": "Withdraw unused capital",
}

TRADE_PLAN_EXAMPLE: dict[str, JsonValue] = {
    "planned_entry": "60000.00",
    "planned_stop": "59000.00",
}

TRADE_CLOSE_EXAMPLE: dict[str, JsonValue] = {
    "realized_pnl": "145.00",
    "actual_exit_price": "63000.00",
    "total_commission": "5.00",
    "funding_result": "0.00",
}

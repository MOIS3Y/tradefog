"""Shared API guidance and coherent examples, separate from handlers."""

from pydantic import JsonValue

API_TAGS: list[dict[str, str]] = [
    {"name": name}
    for name in (
        "Auth",
        "Profiles",
        "Profiles · Assets",
        "Profiles · Instruments",
        "Profiles · Strategies",
        "Profiles · Allocations",
        "Profiles · Operations",
        "Profiles · Trades",
        "Profiles · Trade preparation",
        "Profiles · Trade lifecycle",
        "Profiles · Attachments",
        "Profiles · Analytics",
        "Overview · Trades",
        "Overview · Analytics",
        "Venues",
        "System",
    )
]

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
    "realized_pnl": "18.00",
    "actual_exit_price": "63000.00",
    "total_commission": "0.00",
    "funding_result": "0.00",
}

ASSET_PATCH_EXAMPLE: dict[str, JsonValue] = {
    "risk_stop_capital": "500.00",
}

WALLET_OPERATION_RESPONSE_EXAMPLE: dict[str, JsonValue] = {
    "id": 1,
    "asset_id": 1,
    "kind": "withdrawal",
    "amount": "-100.00",
    "note": "Withdraw unused capital",
    "created_at": "2026-09-10T09:00:00Z",
}

PROFILE_OPERATION_EXAMPLE: dict[str, JsonValue] = {
    **WALLET_OPERATION_RESPONSE_EXAMPLE,
    "asset_symbol": "USDT",
}

STRATEGY_CREATE_EXAMPLE: dict[str, JsonValue] = {
    "name": "Trend continuation",
    "description": "Trade pullbacks in the daily trend.",
    "risk_percent": "1.50",
    "reward_multiple": 3,
}

STRATEGY_PATCH_EXAMPLE: dict[str, JsonValue] = {
    "risk_percent": "1.50",
    "reward_multiple": 3,
}

ALLOCATION_CREATE_EXAMPLE: dict[str, JsonValue] = {
    "asset_id": 1,
    "capital": "400.00",
}

ALLOCATION_PATCH_EXAMPLE: dict[str, JsonValue] = {
    "capital": "400.00",
}

ALLOCATION_EXAMPLE: dict[str, JsonValue] = {
    "id": 1,
    "strategy_id": 1,
    "asset_id": 1,
    "capital": "400.00",
    "is_archived": False,
}

STRATEGY_EXAMPLE: dict[str, JsonValue] = {
    "id": 1,
    "profile_id": 1,
    "name": "Trend continuation",
    "description": "Trade pullbacks in the daily trend.",
    "risk_percent": "1.50",
    "reward_multiple": 3,
    "status": "active",
    "is_archived": False,
    "allocations": [ALLOCATION_EXAMPLE],
}

INSTRUMENT_RULES_EXAMPLE: dict[str, JsonValue] = {
    "price_step": "0.10",
    "qty_step": "0.001",
    "min_qty": "0.001",
    "min_notional": "5.00",
}

MANUAL_INSTRUMENT_EXAMPLE: dict[str, JsonValue] = {
    "mode": "manual",
    "product": "spot",
    "base": {
        "symbol": "BTC",
        "asset_type": "crypto",
        "name": "Bitcoin",
    },
    "quote": {
        "symbol": "USDT",
        "asset_type": "crypto",
        "name": "Tether",
    },
    "price_step": "0.10",
    "qty_step": "0.001",
    "min_qty": "0.001",
    "min_notional": "5.00",
}

INSTRUMENT_PATCH_EXAMPLE: dict[str, JsonValue] = {
    "price_step": "0.10",
    "qty_step": "0.001",
    "min_qty": "0.001",
    "min_notional": "5.00",
}

INSTRUMENT_EXAMPLE: dict[str, JsonValue] = {
    "id": 1,
    "profile_id": 1,
    "exec_symbol": "BTC/USDT",
    "product": "spot",
    "base_asset_id": 2,
    "quote_asset_id": 1,
    "settlement_asset_id": 1,
    "base_asset_type": "crypto",
    "quote_asset_type": "crypto",
    "price_step": "0.10",
    "qty_step": "0.001",
    "min_qty": "0.001",
    "min_notional": "5.00",
    "metadata_updated_at": None,
    "is_active": True,
    "is_archived": False,
}

ATR_REQUEST_EXAMPLE: dict[str, JsonValue] = {
    "value": "4000.00",
    "contributing_date": "2026-09-09",
    "observed_session_range": "1000.00",
    "stale": False,
}

CANDLE_EXAMPLE: dict[str, JsonValue] = {
    "date": "2026-09-09",
    "open": "60000.00",
    "high": "62000.00",
    "low": "58000.00",
    "close": "61000.00",
}

ATR_EXAMPLE: dict[str, JsonValue] = {
    "value": "4000.00",
    "contributing_date": "2026-09-09",
    "observed_session_range": "1000.00",
    "stale": False,
    "source": "manual",
    "observation_time": "2026-09-10T10:00:00Z",
    "session_range_percent": "25.00",
    "candles": [],
}

CHECKLIST_ANSWERS_EXAMPLE: dict[str, JsonValue] = {
    "market_sentiment": "POSITIVE",
    "information_background": "POSITIVE",
    "global_daily_direction": "POSITIVE",
    "local_daily_movement": "POSITIVE",
}

CHECKLIST_EXAMPLE: dict[str, JsonValue] = {
    "market_sentiment": "POSITIVE",
    "information_background": "POSITIVE",
    "global_daily_direction": "POSITIVE",
    "local_daily_movement": "POSITIVE",
    "score": "1.00",
    "direction": "LONG",
    "completeness": "1.00",
    "answered_count": 4,
    "total_count": 4,
    "gauge_position": 100,
    "trend_relationship": "ALIGNED",
    "agrees_with_trade": True,
}

PREPARATION_EXAMPLE: dict[str, JsonValue] = {
    "planned_entry": "60000.00",
    "planned_stop": "59000.00",
    "market_sentiment": "POSITIVE",
    "information_background": "POSITIVE",
    "global_daily_direction": "POSITIVE",
    "local_daily_movement": "POSITIVE",
    "atr_value": "4000.00",
    "atr_source": "manual",
    "atr_contributing_date": "2026-09-09",
    "atr_observation_time": "2026-09-10T10:00:00Z",
    "atr_stale": False,
    "observed_session_range": "1000.00",
}

PLANNING_CONTEXT_EXAMPLE: dict[str, JsonValue] = {
    "price_step": "0.10",
    "quantity_step": "0.001",
    "minimum_quantity": "0.001",
    "minimum_notional": "5.00",
    "reward_multiple": 3,
    "planned_risk_percent": "1.50",
    "target_risk_amount": "6.00",
    "allocation_capital": "400.00",
    "already_reserved_risk": "0.00",
    "remaining_risk_capacity": "400.00",
    "risk_stop_capital": "500.00",
    "wallet_balance": "1000.00",
    "wallet_reserved": "100.00",
    "wallet_available": "900.00",
    "deposit_floor_breach": False,
    "product": "spot",
    "direction": "long",
    "base_asset_id": 2,
    "settlement_asset_id": 1,
    "inventory_asset_id": None,
    "inventory_available": "0.00",
}

STORED_RESERVATION_EXAMPLE: dict[str, JsonValue] = {
    "asset_id": 1,
    "purpose": "position_funding",
    "amount": "360.00",
}

RESERVATION_EXAMPLE: dict[str, JsonValue] = {
    "asset_id": 1,
    "purpose": "position_funding",
    "amount": "360.00",
    "available": "900.00",
}

TRADE_PLAN_RESPONSE_EXAMPLE: dict[str, JsonValue] = {
    "planned_entry": "60000.00",
    "planned_stop": "59000.00",
    "planned_take_profit": "63000.00",
    "stop_distance": "1000.00",
    "take_profit_distance": "3000.00",
    "quantity": "0.006",
    "reward_multiple": 3,
    "planned_risk_percent": "1.50",
    "target_risk_amount": "6.00",
    "planned_risk_amount": "6.00",
    "planned_notional": "360.00",
    "allocation_capital": "400.00",
    "already_reserved_risk": "0.00",
    "remaining_risk_capacity": "394.00",
    "deposit_floor_breach": False,
    "wallet_balance": "1000.00",
    "wallet_reserved": "100.00",
    "wallet_available": "900.00",
    "capital_remaining": "540.00",
    "capital_sufficient": True,
    "atr_value": "4000.00",
    "take_profit_atr_percent": "75.00",
    "fits_atr_limit": True,
    "atr_limit_percent": "75.00",
    "reservations": [RESERVATION_EXAMPLE],
}

SNAPSHOT_EXAMPLE: dict[str, JsonValue] = {
    "id": 1,
    "strategy_capital_id": 1,
    "settlement_asset_id": 1,
    "instrument_symbol": "BTC/USDT",
    "instrument_product": "spot",
    "price_step": "0.10",
    "qty_step": "0.001",
    "min_qty": "0.001",
    "min_notional": "5.00",
    "planned_entry": "60000.00",
    "planned_stop": "59000.00",
    "planned_take_profit": "63000.00",
    "quantity": "0.006",
    "reward_multiple": "3",
    "planned_risk_percent": "1.50",
    "planned_risk_amount": "6.00",
    "planned_notional": "360.00",
    "allocation_capital": "400.00",
    "risk_stop_capital": "500.00",
    "already_reserved_risk": "0.00",
    "remaining_risk_capacity": "400.00",
    "deposit_floor_breach": False,
    "wallet_balance": "1000.00",
    "wallet_reserved": "100.00",
    "wallet_available": "900.00",
    "atr_value": "4000.00",
    "atr_source": "manual",
    "atr_contributing_date": "2026-09-09",
    "atr_observation_time": "2026-09-10T10:00:00Z",
    "atr_stale": False,
    "created_at": "2026-09-10T10:05:00Z",
    "stop_distance": "1000.00",
    "take_profit_distance": "3000.00",
}

TRADE_LIST_EXAMPLE: dict[str, JsonValue] = {
    "id": 1,
    "profile_id": 1,
    "profile_name": "Manual trading",
    "strategy_id": 1,
    "strategy_name": "Trend continuation",
    "instrument_id": 1,
    "exec_symbol": "BTC/USDT",
    "pair_symbol": "BTC/USDT",
    "settlement_symbol": "USDT",
    "trade_date": "2026-09-10",
    "direction": "long",
    "status": "closed",
    "realized_pnl": "18.00",
    "quality_rating": 8,
    "review_completed_at": "2026-09-11T12:00:00Z",
}

TRADE_EXAMPLE: dict[str, JsonValue] = {
    "id": 1,
    "profile_id": 1,
    "strategy_id": 1,
    "instrument_id": 1,
    "trade_date": "2026-09-10",
    "status": "closed",
    "direction": "long",
    "description_markdown": "Daily trend pullback.",
    "quality_rating": 8,
    "review_completed_at": "2026-09-11T12:00:00Z",
    "realized_pnl": "18.00",
    "actual_exit_price": "63000.00",
    "total_commission": "0.00",
    "funding_result": "0.00",
    "submitted_at": "2026-09-10T10:05:00Z",
    "opened_at": "2026-09-10T10:05:00Z",
    "closed_at": "2026-09-11T10:00:00Z",
    "cancelled_at": None,
    "created_at": "2026-09-10T10:00:00Z",
    "preparation": PREPARATION_EXAMPLE,
    "reservations": [STORED_RESERVATION_EXAMPLE],
    "checklist": CHECKLIST_EXAMPLE,
    "plan": TRADE_PLAN_EXAMPLE,
    "atr": ATR_EXAMPLE,
    "snapshot": SNAPSHOT_EXAMPLE,
}

TRAJECTORY_POINT_EXAMPLE: dict[str, JsonValue] = {
    "sequence": 1,
    "trade_id": 1,
    "profile_id": 1,
    "trade_date": "2026-09-10",
    "closed_at": "2026-09-11T10:00:00Z",
    "profile_name": "Manual trading",
    "product": "spot",
    "pair_symbol": "BTC/USDT",
    "direction": "long",
    "result_r": "3.00",
    "outcome": "WIN",
    "cumulative_result_r": "3.00",
    "discipline_x": "0.00",
    "discipline_y": "1.00",
}

REFERENCE_POINT_EXAMPLE: dict[str, JsonValue] = {
    "sequence": 1,
    "cumulative_result_r": "0.00",
}

DISCIPLINE_REFERENCE_EXAMPLE: dict[str, JsonValue] = {
    "x": "3.00",
    "y": "1.00",
}

MONETARY_POINT_EXAMPLE: dict[str, JsonValue] = {
    "sequence": 1,
    "trade_id": 1,
    "profile_id": 1,
    "closed_at": "2026-09-11T10:00:00Z",
    "realized_pnl": "18.00",
    "cumulative_pnl": "18.00",
}

ALLOCATION_MONETARY_EXAMPLE: dict[str, JsonValue] = {
    "strategy_capital_id": 1,
    "settlement_asset_id": 1,
    "settlement_asset_symbol": "USDT",
    "allocation_capital": "400.00",
    "trade_count": 1,
    "gross_profit": "18.00",
    "gross_loss": "0.00",
    "net_pnl": "18.00",
    "allocation_return_percent": "4.50",
    "trajectory": [MONETARY_POINT_EXAMPLE],
}

ANALYTICS_EXAMPLE: dict[str, JsonValue] = {
    "closed_trade_count": 1,
    "reviewed_trade_count": 1,
    "excluded_trade_count": 0,
    "win_count": 1,
    "loss_count": 0,
    "break_even_count": 0,
    "win_rate_percent": "100.00",
    "net_result_r": "3.00",
    "average_result_r": "3.00",
    "average_win_r": "3.00",
    "average_loss_r": "0.00",
    "gross_profit_r": "3.00",
    "gross_loss_r": "0.00",
    "profit_factor_r": None,
    "expectancy_r": "3.00",
    "maximum_drawdown_r": "0.00",
    "current_streak": {
        "outcome": "WIN",
        "count": 1,
    },
    "maximum_winning_streak": 1,
    "maximum_losing_streak": 0,
    "average_quality_rating": "8.00",
    "trajectory": [TRAJECTORY_POINT_EXAMPLE],
    "break_even_reference": [
        {
            "sequence": 0,
            "cumulative_result_r": "0.00",
        },
        REFERENCE_POINT_EXAMPLE,
    ],
    "discipline_available": True,
    "discipline_reward_multiple": 3,
    "discipline_break_even_reference": [
        {
            "x": "0.00",
            "y": "0.00",
        },
        DISCIPLINE_REFERENCE_EXAMPLE,
    ],
    "monetary": [ALLOCATION_MONETARY_EXAMPLE],
}

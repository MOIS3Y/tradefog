# Domain Model

## Ownership

All trading data belongs to a user through TradingProfile.owner_id. There is
no shared staff-managed market catalog. Child records do not duplicate owner
fields; services validate both ownership and same-profile references.

```text
User
└── TradingProfile (bybit / manual)
    ├── TradingAsset → WalletOperation
    ├── TradingInstrument (base / quote / settlement)
    ├── TradingStrategy → StrategyCapital
    └── Trade
        ├── TradePreparation
        ├── TradeSnapshot → TradeReservation
        └── Attachment
```

Bybit imports selected public instrument metadata and required assets; manual
profiles define them themselves. Both have virtual wallets funded explicitly
by the user. Import never creates funds or private exchange connections.

Instrument identity is unique by profile, product and executable symbol.
Its asset references must belong to the same profile; supported products use
quote as settlement. Source availability and user archive state are separate.
Refresh changes execution rules, not identity or historical snapshots.
User records also carry optional contact names/email and audit timestamps;
email is neither a unique login identity nor a verified address.

## User Journal & Capital

- **TradingProfile**: Journal context with a fixed `venue_type`. Has an active/archived
  state. Only archived profiles can be permanently deleted.
- **TradingAsset**: Profile-owned symbol, optional name, type, archive state and
  advisory capital floor. Also the virtual account denomination. Balance,
  allocated capital and reservations are derived, never manually overwritten.
  Both instrument creation paths create missing assets atomically; a user may
  also add an asset directly in manual profiles. Bybit identities come only
  from instrument imports. No implicit funding.
- **Wallet**: A view of profile assets, not a persisted container.
- **WalletOperation**: Explicit ledger entries for `DEPOSIT` and `WITHDRAWAL`.
  Initial capital is represented as an initial deposit operation. Its kind,
  amount, and creation time are immutable; only its explanatory note may be
  corrected.
- **TradingStrategy**: Defines risk discipline through two independent values.
  `risk_percent` accepts decimal values from `0.01%` through `100%` and sets the
  monetary size of `1R` for every allocation. `reward_multiple` is the right
  side of the canonical `1:N` ratio and is a whole number from `3` through
  `100`. The left side is always one and is never entered separately.
- **StrategyCapital**: Fixed capital allocated from a `TradingAsset` to a
  `TradingStrategy`. Its amount is locked after the first submitted trade that
  uses it; a materially different risk tier requires a new strategy or
  allocation rather than rewriting history.
- **Attachment**: Private image metadata owned transitively through its
  `Trade`; file content remains outside the database and is never public.

### Risk & Capital Invariants

- **Fixed Monetary Risk (1R)**:
  `1R = StrategyCapital.allocated_capital * (TradingStrategy.risk_percent / 100)`
- **Canonical Reward Rule**: `take_profit_distance = stop_distance * N`, where
  `N` is the strategy's whole reward multiple from `3` through `100`. For
  example, a `5.5%` risk and `N = 3` risk `5.5%` of the fixed allocation and
  target three times that monetary risk.
- **Take-Profit Price**: Derived deterministically from entry, stop, and reward
  multiple. Cannot be edited independently.
- **Position Sizing**: Quantity rounds down to the venue step, so executable
  monetary loss at the stop never exceeds the target `1R`.
- **Wallet Reservations**: Moving a trade to `PENDING` or `OPEN` locks the
  requirements in `TradeReservation`, not a universal notional.

## Trade Lifecycle

```text
DRAFT ──► PENDING ──► OPEN ──► CLOSED
  │          │         │
  ▼          ▼         ▼
CANCELLED  CANCELLED  CANCELLED
```

1. **DRAFT**: Editable trade workspace. Checklist, plan, and ATR can be
   updated freely.
2. **PENDING**: Order placed with external broker. Freezes an immutable
   `TradeSnapshot`, records `submitted_at`, and reserves capital in the wallet.
3. **OPEN**: Order filled. Position is active.
4. **CLOSED**: Position exited. `closed_at` and final signed net realized P&L
   in the snapshotted settlement asset are recorded.
5. **CANCELLED**: Draft or pending entry cancelled before fill. Open trades must close with actual P&L. Releases wallet
   reservations.

## Trade Snapshot & Invariants

Transitioning from `DRAFT` to `PENDING` or `OPEN` atomically creates an
immutable `TradeSnapshot`:

- Identifies the exact `StrategyCapital` and settlement `Asset` used by the
  trade, keeping analytical cohorts stable after archival.
- Freezes planned entry, stop loss, take profit, position quantity, and planned
  notional.
- Freezes strategy risk percent, reward multiple, allocation capital, planned
  1R risk amount, and ATR context (source and calculated value).
- Verifies that `TradingInstrument.settlement_asset` matches the strategy's
  settlement `TradingAsset`.
- Verifies all required inventory and settlement reserves are available.

After the snapshot exists, direction, checklist, ATR, and position fields are
locked. Notes, attachments, review completion, and an optional integer quality
rating from `1` through `10` remain editable without changing the plan.

## Directional Checklist & Setup Assessment

Trades evaluate 4 standard directional observations with fixed weights:

| Observation | Weight | Values |
| --- | ---: | --- |
| Broad Market Sentiment | 1 | Bearish (-1), Neutral (0), Bullish (+1) |
| Information Background | 1 | Negative (-1), Neutral (0), Positive (+1) |
| Global D1 Direction (~20-30 candles) | 3 | Down (-1), Sideways (0), Up (+1) |
| Local D1 Movement (~5-7 candles) | 2 | Down (-1), Sideways (0), Up (+1) |

- **Score**: Weighted sum divided by maximum potential weight (7.0), resulting
  in a normalized directional assessment between `-1.0` (Short) and `+1.0` (Long).
- **Advisory Role**: Disagreement between checklist assessment and chosen trade
  direction is recorded but does not block trade execution.

## Typed Preparation and Reservations

TradePreparation stores nullable entry/stop, four checklist answers and ATR
facts. Partial inputs can be saved; complete plans are validated on submission.
Computed TP, size, checklist assessment and ATR percentages are not duplicated.
Preparation is retained and locked after submission; snapshot and reservation
rows are written atomically.

Spot/cash long and virtual 1x perpetual reserve notional in settlement currency.
Spot/cash short is sale of owned inventory followed by full-quantity buyback:
reserve base quantity plus planned quote loss. Sale proceeds are never credited
as spendable money. No separate base-asset strategy allocation is required.
Inventory stays in the virtual balance but is unavailable until buyback.

Reservation rows are immutable; only pending/open trades count toward reserved
funds. Closing uses actual exit and net P&L exactly once, even if slippage
exceeds the planned reserve and leaves a negative virtual balance. Commission
and funding fields are context, not additional deductions from net P&L.
Partial quantities and borrowed inventory are outside v1.
Monetary reports retain exact allocation/profile/asset cohorts; cross-profile
comparisons use dimensionless R without automatic currency aggregation.

## Unified asset setup

Manual instruments accept separate base and quote symbols, reusing normalized
profile identities and requiring a type only for new assets. Bybit imports
explicit base/quote/settlement codes; symbols are never split heuristically.
Instrument display names derive from the pair and product; only assets have
optional descriptive names. Settlement identity remains explicit, with the
existing restriction that supported products settle in quote.

The wallet can hide never-used zero-balance assets. Ledger operations,
allocations and trade history keep an asset visible even after its balance
returns to zero. Hiding is presentation only and never releases reservations.
Archived assets cannot accept new activity; existing names and archive choices
are never overwritten by an import. Active instruments/allocations, funds or
reservations prevent asset archival. References prevent permanent deletion.

Portfolio-wide aggregation and historical valuation are outside this change;
no aggregate wallet table is introduced.

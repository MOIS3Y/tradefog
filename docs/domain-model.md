# Domain Model

## Ownership Zones

The domain model is divided into two distinct ownership zones:

1. **Shared Reference Catalog**: Staff-managed common directory (`Asset`,
   `TradingPair`, `Venue`, `VenueInstrument`, `VenueWalletAsset`). Regular
   users have read-only access.
2. **User Journal**: Owner-scoped entities (`TradingProfile`, `Wallet`,
   `WalletAsset`, `WalletOperation`, `TradingStrategy`, `StrategyCapital`,
   `Trade`, `TradeSnapshot`, `Attachment`).

```text
Shared Catalog (Staff-managed)
├── Asset                          # Reusable symbol and type (Crypto/Equity/Fiat)
├── TradingPair                    # Canonical BASE/QUOTE market
└── Venue                          # Exchange or Broker destination
    ├── VenueInstrument            # Executable product/market on a venue
    └── VenueWalletAsset           # Assets permitted in wallets on this venue

User Journal (Owner-scoped via TradingProfile.owner)
└── TradingProfile                 # Top-level trading context (bound to 1 Venue)
    └── Wallet                     # 1:1 relation with TradingProfile
        ├── WalletAsset            # Balance and floor for a venue-capable asset
        │   └── WalletOperation    # Immutable deposit / withdrawal log
        ├── TradingStrategy        # Risk % and Reward multiple
        │   └── StrategyCapital    # Fixed capital allocated per WalletAsset
        └── Trade                  # Trade draft, open, closed, or cancelled
            ├── TradeSnapshot      # Write-once plan & ATR snapshot
            └── Attachment         # Private image metadata and storage key
```

`TradingProfile.owner` is the single root of ownership for all journal records.
No child record duplicates user ownership fields.

## Shared Reference Catalog

- **Asset**: Global identity, unique normalized symbol (e.g. `BTC`, `USD`),
  display name, and asset type (`CRYPTO`, `EQUITY`, `FIAT`).
- **TradingPair**: Logical market pairing one base `Asset` and one quote
  `Asset` (`BASE/QUOTE`).
- **Venue**: Execution destination (e.g. `Bybit`, `Interactive Brokers`).
  Carries no market class; markets are derived from venue instruments.
- **VenueInstrument**: Executable instrument on a specific `Venue` for a
  `TradingPair`. Stores execution symbol, price step, quantity step, minimum
  order size, and product kind (`SPOT`, `PERPETUAL_FUTURE`, `CASH_EQUITY`).
- **VenueWalletAsset**: Links a `Venue` to an `Asset` capable of being held
  in a wallet on that venue.

## User Journal & Capital

- **TradingProfile**: Journal context bound to one `Venue`. Has an active/archived
  state. Only archived profiles can be permanently deleted.
- **Wallet**: 1:1 container of assets for a `TradingProfile`.
- **WalletAsset**: Held balance for a `VenueWalletAsset`. Tracks current
  balance, derived reservations, and an advisory `risk_stop_capital` floor.
- **WalletOperation**: Explicit ledger entries for `DEPOSIT` and `WITHDRAWAL`.
  Initial capital is represented as an initial deposit operation. Its kind,
  amount, and creation time are immutable; only its explanatory note may be
  corrected.
- **TradingStrategy**: Defines risk discipline through two independent values.
  `risk_percent` accepts decimal values from `0.01%` through `100%` and sets the
  monetary size of `1R` for every allocation. `reward_multiple` is the right
  side of the canonical `1:N` ratio and is a whole number from `3` through
  `100`. The left side is always one and is never entered separately.
- **StrategyCapital**: Fixed capital allocated from a `WalletAsset` to a
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
  required notional capital.

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
5. **CANCELLED**: Order cancelled before fill or aborted. Releases wallet
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
- Verifies that `VenueInstrument.settlement_asset` matches the strategy's
  settlement `WalletAsset`.
- Verifies that available wallet balance is sufficient for required notional.

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

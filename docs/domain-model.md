# Tradefog domain model

## Ownership

All journal data belongs to one authenticated user. Public registration is not
part of the initial product; administrators create accounts. Every venue,
catalog product, asset, instrument, profile selection, strategy, trade,
snapshot, and attachment query is scoped by owner, either directly or through
its owned parent.

The custom user model derives from Django's `AbstractUser` so it can evolve
without a disruptive user-model migration later.

## Venue catalog and profile hierarchy

The domain separates reusable venue facts from profile-specific financial and
journal state:

```text
User
├── Venue
│   ├── VenueProduct
│   │   └── VenueInstrument
│   └── VenueAsset
└── TradingProfile
    ├── Venue and market class
    ├── ProfileProduct → VenueProduct
    │   └── ProfileInstrument → VenueInstrument
    │       └── MarketDataFeed
    │           └── DailyCandle
    ├── WalletAsset → VenueAsset
    │   └── WalletOperation
    ├── TradingStrategy
    └── Trade → ProfileInstrument
```

There is no cross-venue asset or instrument catalog, explicit market
activation, or separate trading-account layer. `Venue` is the reusable public
instrument boundary. `TradingProfile` is the independent financial and
journal boundary and never duplicates the venue catalog.

## Venues and trading profiles

`Venue` is an owner-scoped exchange, broker, or other execution destination.
It has a name, an optional website URL, and an instrument adapter kind that
defaults to `MANUAL`. A venue may support more than one market family, so
Crypto or Equity does not belong to the venue itself.

Venues and their instrument catalogs are managed independently from profiles.
An active venue can be reused by several profiles and cannot be archived while
an active profile references it. Archived venues remain attached to historical
profiles but are unavailable for new profile selection.

`TradingProfile` is the user's top-level trading context, such as "Bybit Main"
or "IBKR Equities". It belongs to one venue and fixes one market class:
Crypto or Equity. Market class directly determines which products can be
configured; the user does not separately activate market families.

A profile selects products and instruments from its venue and owns its virtual
wallet, strategies, and trades. Multiple profiles at the same venue share
catalog identity while retaining independent balances, risk, configuration,
and journal history. Archiving a profile removes the financial context from
normal new activity without changing venue catalog facts or historical trades.

## Venue products, assets, and instruments

`VenueProduct` is a catalog section under one venue. Its kind is Spot, Linear
Perpetual, or Cash Equity and is unique within that venue. It owns instrument
catalog and adapter synchronization state. Manual venues expose the same
sections but their instruments are maintained by the user.

`VenueAsset` is an internal venue-scoped identity with a normalized symbol,
asset class, and optional descriptive metadata. Symbols are unique within one
venue without regard to letter case. There is no standalone asset-management
screen. Manual instrument entry creates or reuses its base, quote, and
settlement venue assets; adapters normalize provider metadata into the same
records.

`VenueInstrument` belongs to one venue product and uses venue assets for its
base, quote, and settlement sides. It stores the venue execution symbol, price
and quantity steps, minimum order rules, availability, import provenance, and
archive or delisting state. The canonical display is `BASE/QUOTE`. A catalog
sync never deletes an instrument referenced by a profile or trade. Product,
base, quote, settlement, and execution identity are not mutated in place after
use; an identity change creates a replacement instrument.

Venue product kind is unique per venue, venue asset symbol is unique per venue
without regard to case, and an active base, quote, and settlement combination
is unique per venue product. A non-empty execution symbol is also unique within
its venue product.

The initial compatibility matrix is:

| Market class | Product | Base | Quote | Settlement | Directions |
| --- | --- | --- | --- | --- | --- |
| Crypto | Spot | Crypto | Crypto or Fiat | Quote | LONG |
| Crypto | Linear Perpetual | Crypto | Crypto or Fiat | Explicit | LONG, SHORT |
| Equity | Cash | Equity | Fiat | Quote | LONG |

Base and quote must differ. Spot and Cash Equity derive settlement from the
quote asset. A Linear adapter supplies settlement when it can; otherwise the
user must select it explicitly. An imported pair with unresolved settlement
cannot become active or be used by a trade. Symbols are never parsed to guess
settlement, and USD, USDT, and USDC are distinct without an explicit future
conversion policy.

Venue instrument adapters synchronize this reusable catalog for every
supported product, including the full public Spot or Linear list when the
adapter provides it. Missing provider instruments become unavailable or
delisted rather than being deleted. Import never selects instruments for a
profile and never makes an automatic market-data or execution choice.

## Profile product and instrument selection

`ProfileProduct` links a profile to a compatible `VenueProduct`. A Crypto
profile may select Spot and Linear Perpetual from its venue; an Equity profile
may select Cash Equity. Future authenticated execution configuration belongs
to this profile product, not to the venue catalog.

`ProfileInstrument` links a profile product to one instrument from the same
venue product. It represents the deliberately enabled working subset of the
venue catalog, so an imported venue with thousands of instruments does not
flood trade selectors. The selection can be archived without changing the
shared venue instrument. Trades reference this profile selection rather than
referencing the venue catalog directly.

A profile product must reference a venue product owned by the profile's venue.
A profile instrument must reference an instrument from that exact venue
product. Each product kind and each active instrument selection are unique
within one profile.

## Virtual wallet

`WalletAsset` belongs to a profile and references one `VenueAsset` from the
profile's venue. The same venue USDT identity can back independent wallet
balances and reservations in several profiles. Wallet choices are the unique
base, quote, and settlement assets exposed by the profile's active instrument
selections, restricted to asset classes eligible for wallet accounting. Only
wallet assets also used as settlement by an active profile instrument can be
selected by a strategy.

Wallet funds are introduced and removed only through explicit `DEPOSIT` and
`WITHDRAWAL` operations on a selected wallet asset. An operation stores its
wallet asset, amount, optional note, and creation time. It is a journal fact,
not an exchange action. A wallet asset with activity or a strategy or trade
settled in it cannot be removed.

```text
wallet_balance = deposits - withdrawals + closed_trade_realized_pnl
available_balance = wallet_balance - reserved_notional
```

Pending-entry and open trades reserve their snapshotted planned notional at
the fixed `1x` strategy. Drafts reserve nothing. A withdrawal cannot exceed
positive available balance. Closing a trade is never rejected because its
recorded P&L may legitimately make a virtual balance negative.

## Trading strategies

`TradingStrategy` is one fixed strategic risk cohort inside a profile. It
stores its name, description, settlement wallet asset, strategic capital,
risk percent, absolute risk stop, and operational status. Several strategies
may share the same profile wallet.

The selectable settlement assets for a strategy are the intersection of the
profile wallet and settlement assets of active profile instrument selections.
A strategy can use several products and instruments, but every selected
instrument must have exactly the same settlement asset. Unlike currencies are
never treated as equivalent.

Strategy settlement, strategic capital, risk percent, and risk stop remain
correctable while every strategy trade is a draft and become locked after the
first submitted trade. The strategy name and description remain editable.

The first version excludes FX, spot margin, equity short selling, configurable
leverage, inverse contracts, expiring futures, options, and contract
multipliers.

## Risk sizing

Future trade risk uses the fixed strategic capital:

```text
risk_amount = strategic_capital * risk_percent / 100
take_profit_amount = risk_amount * 3
```

Profits, losses, and wallet operations never resize monetary `1R`. A trader
who changes strategy scale creates a new strategy and may archive the old
one. The absolute `risk_stop_capital` identifies the strategy-equity level at
which the strategy should stop.

## Strategy status

Strategy status has four values:

- `ACTIVE`;
- `AT_RISK`;
- `RISK_STOPPED`;
- `ARCHIVED`.

Strategy equity is a strategy result, not wallet funds:

```text
strategy_equity = strategic_capital + sum(strategy realized_pnl)
```

Pending and open trades reserve their snapshotted planned risk:

```text
reserved_risk =
    sum(planned_risk_amount for PENDING_ENTRY and OPEN trades)

worst_case_equity = strategy_equity - reserved_risk
```

An archived strategy always reports `ARCHIVED`. Otherwise it is
`RISK_STOPPED` when strategy equity is at or below the stop, `AT_RISK` when
strategy equity is above the stop but worst-case equity is at or below it,
and `ACTIVE` otherwise. Restoring an archived strategy recalculates its
financial status.

Financial facts are the source of truth. Focused domain services update the
persisted operational status after relevant capital and trade transitions.

The risk stop is advisory for manual activity. A draft can always be saved.
A transition to pending or open records an explicit risk-stop breach after a
clear warning. Insufficient wallet availability is a hard constraint for a
prospective pending or open trade because the virtual wallet cannot provide
the required `1x` notional.

## Strategy and instrument compatibility

A trade belongs to one strategy and one profile instrument selection. Both
must belong to the same profile. The underlying venue instrument must belong
to that profile's venue and its settlement asset must exactly match the
strategy settlement wallet asset. Product is derived from the instrument
selection rather than duplicated on the trade.

```text
profile_instrument.profile = strategy.profile
profile_instrument.venue_instrument.venue_product.venue =
    strategy.profile.venue
profile_instrument.venue_instrument.settlement_asset =
    strategy.settlement_wallet_asset.venue_asset
```

Compatible querysets hide invalid instrument selections in the interface.
Draft persistence and every transition to `PENDING_ENTRY` or `OPEN` repeat
the invariant in a domain service so stale forms, crafted requests, and
future execution adapters cannot bypass it. For example, a USD strategy
cannot use BTC/USDT even when its profile wallet also contains USDT.

## Position plan

The trader supplies direction, planned entry, and planned stop. The reward
multiple is the code-defined constant `3`.

```text
LONG distance = entry - stop
LONG take_profit = entry + distance * reward_multiple

SHORT distance = stop - entry
SHORT take_profit = entry - distance * reward_multiple

quantity = risk_amount / distance
```

Quantity is rounded down to the market's quantity step so the resulting plan
does not exceed the snapshotted risk. Plans below minimum quantity or notional
are invalid or clearly marked. A plan whose notional exceeds the wallet's
available balance in its settlement asset is infeasible at `1x`; leverage is
never increased to make it fit.

Financial, price, quantity, percentage, P&L, and R calculations use decimal
arithmetic with explicit rounding.

## Trade lifecycle

The initial lifecycle is:

- `DRAFT`;
- `PENDING_ENTRY`;
- `OPEN`;
- `CLOSED`;
- `CANCELLED`.

A draft is an analyzed setup that may never be traded and reserves no funds.
`PENDING_ENTRY` represents a placed but unfilled manual order and reserves
planned notional in the profile wallet. `OPEN` retains that reservation.
Cancelling an unfilled order or closing a position releases it and
recalculates strategy status.

Lifecycle changes are coordinated by focused operations such as
`submit_trade`, `open_trade`, `cancel_trade`, and `close_trade`. These
operations form the shared boundary used by HTTP views and the manual journal.

When a trade leaves `DRAFT`, it snapshots enough decision context to remain
reproducible:

- planned risk percent and amount;
- reward multiple;
- strategy equity and fixed strategic capital;
- risk-stop capital;
- already reserved risk;
- remaining risk capacity;
- risk-limit breach state;
- wallet balance, reservation, and available balance;
- position-plan material values;
- the relevant ATR context.

Later wallet operations, strategy corrections, and other trades do not rewrite
these snapshots.

## Closing and realized result

The first version does not model partial fills or exits. A partially closed
position remains `OPEN`. Once fully closed, it stores one final signed net
`realized_pnl` in strategy currency. This number is authoritative and already
includes fees, slippage, stops, targets, funding, and manual exits.

An optional actual exit price is reference data. Optional total commission
and signed funding result explain the net outcome but are not subtracted from
it again. Realized P&L changes the profile wallet balance for the settlement
asset and the strategy's virtual equity when closure is registered in
Tradefog.

A retrospectively entered trade belongs analytically to its `trade_date` but
changes wallet balance and strategy equity at registration time. Correcting
journal facts
recalculates analytics and current strategy state without rewriting snapshots
on other submitted trades.

## R results and quality trajectory

The normalized result is:

```text
result_r = realized_pnl / planned_risk_amount
```

Aggregate statistics include:

```text
net_result_r = sum(result_r)
average_result_r = net_result_r / closed_trade_count
```

The X/Y trajectory represents full-stop and full-target equivalents while
supporting partial or manual outcomes:

```text
X += abs(min(result_r, 0))
Y += max(result_r, 0) / reward_multiple
```

The break-even line is:

```text
Y = X / reward_multiple
```

With the fixed strategy it is `Y = X / 3`. There is no target line. The
coordinate after each deterministically ordered closed trade is preserved or
reproducibly derived so charts can display the path rather than only the
final point.

For filtered analytics, closed trades are selected by editable `trade_date`,
ordered deterministically, and recalculated from `(0, 0)`. Counts, streaks,
net R, and average R use the same selection.

## Checklist representation

The first checklist has a fixed application-defined shape. Its assessment
logic is a focused domain calculation rather than template or HTTP-view code.
Schema and scoring changes use deliberate migrations so historical answers
are not silently discarded.

The four nullable directional answers and their weights are:

```text
broad market sentiment = 1
information background = 1
global D1 direction = 3
local D1 movement = 2
```

Each answered value is negative, neutral, or positive and therefore maps to
`-1`, `0`, or `1`. The internal signed score is:

```text
score = sum(answer_value * weight) / 7
```

Unanswered values add zero to the numerator while retaining their possible
weight in the denominator. Completeness is the answered question count over
the four fixed questions and is shown separately. The relationship between
global and local D1 observations is derived without another weighted answer.

One score ranges from `SHORT` through neutral to `LONG`. It is advisory,
remains independent of the selected trade direction, and does not block a
trade when the two disagree. Draft answers become read-only when the trade
leaves `DRAFT`. Text, prices, and raw ATR do not contribute to the directional
score.

An owner-defined strategy checklist is a separate future concept. It measures
setup strength relative to a selected strategy rather than predicting market
direction and requires immutable historical strategy versions.

## Market-data feeds, snapshots, and ATR

Market observations belong to one profile instrument selection. A selection
has one active `MarketDataFeed`; previous feeds may remain inactive so candles
from different providers are never mixed. A feed stores its provider,
external symbol, provider-specific category, refresh state, and dated closed
daily candles. The supported sources are `MANUAL`, `BYBIT`, and
`TWELVE_DATA`, with `MANUAL` as the default.

Automatic data is never enabled merely because an instrument was imported
into a venue catalog. The user must explicitly select and configure an
automatic source for the profile instrument.
Manual feed candles can be added, corrected, and removed by the user.
Automatic feed candles are read-only journal cache and change only through
their provider adapter. Market-data symbols and reported quote currencies do
not determine the execution pair's settlement asset.

A dated closed daily candle stores OHLC prices, source observation time, and
provider trading date. Provider session semantics remain attached to the
feed; for example, Bybit daily candle dates identify UTC sessions.

True Range and standard `ATR(14)` are deterministic calculations over closed
daily candles. The initial ATR is the mean of the first 14 True Range values,
which requires 15 closed candles, and later values use Wilder smoothing. For
a trade date `D`, only candles before `D` contribute. Current-session range
remains separate and may be compared with ATR and the advisory 75% reference.

The draft workspace also compares the exact planned price movement from entry
to take profit with the same reference:

```text
target_movement = abs(take_profit - entry)
target_atr_percent = target_movement / ATR(14) * 100
fits_reference = target_atr_percent <= 75
```

This comparison is advisory. It does not change the take profit, position
size, risk, or lifecycle validity.

The latest successful provider refresh, failure state, and still-forming
session high and low are cached per feed. Provider failure preserves stored
candles and marks their context stale. When a trade leaves `DRAFT`, available
ATR value, contributing date, feed identity, current-session range,
observation time, and stale state are frozen with the other decision facts.
Missing or stale market context remains advisory and does not block the
manual trade lifecycle.

## Attachments

Each trade may have one optional description containing Markdown. The
description is editable in every lifecycle state so premarket observations,
execution notes, errors, and conclusions can accumulate in one document. A
review-completion timestamp may be set only after the trade is closed. It is
a user-controlled review fact, not another trade lifecycle state.

Screenshots and other trade attachments are private journal data associated
directly with an owned trade. Uploads are allowed in every lifecycle state.
They are served only after an authenticated ownership check; public sharing
and public media URLs are not part of the initial model. The configured
per-file size limit may be disabled by a self-hosted deployment, while the
application retains a fixed safe allowlist for inline image and PDF content.

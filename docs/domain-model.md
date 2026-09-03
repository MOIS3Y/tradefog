# Tradefog domain model

## Ownership

The domain has two ownership zones:

- **User journal**: profiles, wallet assets and operations, strategies,
  trades, snapshots, checklist answers, and attachments belong to one
  authenticated user.
- **Shared reference catalog**: assets, trading pairs, venues, venue
  instruments, and venue wallet assets form a common directory for the whole
  installation. Only staff members may create or edit catalog records; all
  authenticated users may read and reuse them.

`TradingProfile.owner` is the single ownership root for all journal data.
Child records (`WalletAsset`, `WalletOperation`, `TradingStrategy`, `Trade`,
`TradeSnapshot`, checklist answers, and attachments) carry no redundant owner
field; their owner is reached transitively through the profile, or through a
trade that belongs to a profile. This keeps one source of truth for ownership
and avoids duplicated owner fields on every table.

All journal queries go through a single centralized scoping manager that adds
`profile__owner=current_user` (or the equivalent owner-scoped filter). Journal
services, views, and selectors must route through that manager rather than
re-implementing ownership checks. An object is created only under the current
user's own profile, so no path can read or mutate another user's journal data.

Public registration is not part of the initial product; administrators create
accounts. The custom user model derives from Django's `AbstractUser` so it can
evolve without a disruptive user-model migration later.

## Reference catalog and user journal

The domain separates a shared, staff-managed reference catalog from each
user's journal:

```text
Reference catalog (staff-managed, shared)
├── Asset                          # global identity and unambiguous type
├── TradingPair                    # reusable BASE/QUOTE relationship
├── Venue
│   ├── VenueInstrument            # executable market on one venue
│   └── VenueWalletAsset           # assets that can be held in a wallet on this venue

User journal (owner-scoped via TradingProfile.owner)
└── TradingProfile
    └── Wallet                     # 1:1 with profile; groups wallet assets
        ├── WalletAsset            # balance for one venue-capable asset
        │   └── WalletOperation
        ├── TradingStrategy
        └── Trade
            └── TradeSnapshot      # write-once, created at draft → pending
```

There is no per-user or per-venue asset or pair duplication. The shared
catalog is the single source of executable instrument facts. Market data is
not persisted; candles are fetched on demand in the trade workspace and only
an ATR decision snapshot is stored on a submitted trade.

## Venues and the shared catalog

`Venue` is a shared, staff-managed exchange, broker, or other execution
destination. It has a name and an optional website URL. A venue carries no
market class itself; its supported markets are derived from the products of
its instruments. A venue may therefore host Crypto and Equity instruments
together without duplication.

The catalog is deliberately curated rather than bulk-imported: users add only
the instruments they actually trade. A user who needs a new asset, pair,
venue, or venue instrument asks a staff member to create it. Regular users
read and reuse the shared catalog but cannot create or edit its records.

`TradingProfile` is the user's top-level trading context, such as "Bybit Main"
or "Equities". It is bound to exactly one `Venue`, owns the user's virtual
wallet, strategies, and trades, and reuses that venue's shared instruments
without copying catalog facts. Profiles share catalog identity while retaining
independent balances, risk, configuration, and journal history.

## Assets, trading pairs, and venue instruments

`Asset` is a shared, globally reusable identity with a normalized symbol, a
display name, and an unambiguous asset type: Crypto, Equity, or Fiat. A symbol
identifies one asset installation-wide, so the BTC used on one venue is the
same `Asset` as on another. There is no standalone asset-management screen and
assets are maintained only by staff; manual instrument entry reuses existing
assets.

`TradingPair` is the shared, reusable logical market that combines one base
and one quote `Asset`. The canonical display is `BASE/QUOTE`. It carries no
execution parameters and is entered once for the whole installation.

`VenueInstrument` is the executable market on one venue for one product. It
links a `TradingPair` to a `Venue` and stores the venue execution symbol,
price and quantity steps, minimum order rules, availability, and archive or
delisting state. Because execution parameters differ per venue and product,
`VenueInstrument` is the only record that holds the per-market symbols and
steps; the underlying asset and pair remain shared and are never duplicated.
Product kind is Spot, Perpetual Future, or Cash Equity and implies the market
class: Spot and Perpetual Future are Crypto, Cash Equity is Equity.

`VenueWalletAsset` links a venue to the shared assets that can be held in a
wallet on that venue. It is a deliberate subset rather than a derivation: not
every available asset is wallet-capable there, and a profile wallet may only
reference these assets.

Asset symbol is unique installation-wide without regard to letter case. A base
and quote combination is unique per `TradingPair`, and an active base, quote,
and product combination is unique per venue. A non-empty execution symbol is
unique within its venue.

The initial compatibility matrix is:

| Market class | Product | Base | Quote | Settlement | Directions |
| --- | --- | --- | --- | --- | --- |
| Crypto | Spot | Crypto | Crypto or Fiat | Quote | LONG |
| Crypto | Perpetual Future | Crypto | Crypto or Fiat | Explicit | LONG, SHORT |
| Equity | Cash | Equity | Fiat | Quote | LONG |

Base and quote must differ. Spot and Cash Equity derive settlement from the
quote asset. A Perpetual Future venue instrument supplies settlement when it
can; otherwise the user must select it explicitly. An instrument with
unresolved settlement cannot be used by a trade. Symbols are never parsed to
guess
settlement, and USD, USDT, and USDC are distinct without an explicit future
conversion policy.

## Direct instrument reference

Trades reference a shared `VenueInstrument` directly. Because the catalog is
curated rather than bulk-imported, there is no separate "working subset"
selection layer; the catalog already contains only instruments the user
trades. A trade therefore points straight at the venue instrument it concerns.

## Virtual wallet

`Wallet` is the profile's wallet and is strictly one-to-one with its
`TradingProfile`. It holds no money itself; it groups the wallet assets that
carry balances. Because a profile is bound to one venue, the wallet only
offers the assets that the venue exposes as wallet-capable through
`VenueWalletAsset`. A "global wallet" in the interface is a UI-only aggregation
over the user's profile wallets; it is not a separate stored entity and does
not create a second ownership root.

`WalletAsset` belongs to one wallet and references a `VenueWalletAsset` (rather
than a bare `Asset`), so its asset is structurally guaranteed to be
venue-capable for the profile's venue. The same USDT identity can back
independent wallet balances in several profiles. Only wallet assets that are
also used as settlement by a traded instrument can be selected by a strategy.

Wallet funds are introduced and removed only through explicit `DEPOSIT` and
`WITHDRAWAL` operations on a selected wallet asset. An operation stores its
wallet asset, amount, optional note, and creation time. It is a journal fact,
not an exchange action. A wallet asset with activity or a strategy or trade
settled in it cannot be removed.

```text
wallet_balance    = deposits - withdrawals + closed_trade_realized_pnl
reserved_notional = SUM(snapshot.planned_notional)
                    WHERE trade.status IN (PENDING_ENTRY, OPEN)
available_balance = wallet_balance - reserved_notional
```

Reservation is derived state, not a stored record. It is the live sum of the
frozen `planned_notional` from `TradeSnapshot` rows whose trade is still
`PENDING_ENTRY` or `OPEN`. Drafts reserve nothing. Because the reserving
amount is read from the immutable snapshot, it never fluctuates while a trade
reserves funds. A trade releases its reservation simply by leaving
`PENDING_ENTRY` or `OPEN` (moving to `CLOSED` or `CANCELLED`): it then drops
out of the summation, so no manual reservation bookkeeping is needed.

`available_balance` is derived across several tables, so a withdrawal cannot
exceed the positive available balance, and a pending or open trade must fit in
the wallet at `1x`; both are enforced in a focused domain service inside a
database transaction rather than by a database `CHECK` constraint. Closing a
trade is never rejected because its recorded P&L may legitimately make a
virtual balance negative.

## Trading strategies

`TradingStrategy` is one fixed strategic risk cohort inside a profile. It
stores its name, description, settlement wallet asset, strategic capital,
risk percent, absolute risk stop, and operational status. Several strategies
may share the same profile wallet.

The selectable settlement assets for a strategy are the intersection of the
profile wallet and the settlement assets of the instruments the strategy
trades. A strategy can use several products and instruments, but every
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

A trade belongs to one strategy and one profile. The profile is bound to one
venue, so a trade uses only that venue's instruments. The instrument's
settlement asset must exactly match the strategy settlement wallet asset, and
the strategy settlement wallet asset must belong to the profile wallet and be
venue-capable on the profile's venue. Product is derived from the instrument
rather than duplicated on the trade.

```text
profile.venue == trade.venue_instrument.venue
trade.venue_instrument.settlement_asset =
    strategy.settlement_wallet_asset.venue_wallet_asset.asset
strategy.settlement_wallet_asset ∈ profile.Wallet.WalletAsset
```

Compatible querysets hide invalid instrument choices in the interface. Draft
persistence and every transition to `PENDING_ENTRY` or `OPEN` repeat the
invariant in a domain service so stale forms, crafted requests, and future
execution adapters cannot bypass it. For example, a USD strategy cannot use
BTC/USDT even when its profile wallet also contains USDT, and a profile bound
to one venue cannot trade another venue's instrument.

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

## Decision snapshot

The frozen decision context is a separate write-once entity, `TradeSnapshot`,
in a one-to-one relationship with its `Trade`. It is created atomically in the
same database transaction as the `DRAFT → PENDING_ENTRY` transition and is
never mutated afterwards.

The snapshot stores the working fields it copies at that moment, so the
authoritative plan, risk, wallet, and ATR facts live in the snapshot rather
than in editable `Trade` fields:

- the position plan: entry, stop, take profit, quantity, reward multiple;
- the risk plan: risk percent, risk amount, planned notional, strategy equity,
  fixed strategic capital, risk-stop capital, already reserved risk, remaining
  risk capacity, and risk-limit breach state;
- the wallet context: balance, already-reserved notional, and available
  balance;
- the ATR context.

Because the snapshot freezes the plan, a `PENDING_ENTRY` trade is cancellable
but not re-plannable: the reserving `planned_notional` never fluctuates while
the trade reserves funds. `Trade` working fields are locked once the snapshot
exists, enforced by the same domain service that owns the transition.

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

## Market data, snapshots, and ATR

Market data is not persisted in the database. When the user opens or refreshes
a trade in the workspace, the journal fetches the last closed daily candles
on demand from the selected provider and computes `ATR(14)` in the moment.
The supported providers are `BYBIT` and `TWELVE_DATA`; manual candle
maintenance does not exist. Fetched candles are a transient request result and
are never written back to the catalog.

When an instrument has no available provider source, the user may enter the
ATR value directly. The snapshot therefore records an ATR source of `AUTO`
(computed from live provider candles) or `MANUAL` (a user-entered value). An
instrument with no source and no entered value reports ATR as `N/A`. Market
data never determines the execution pair's settlement asset.

True Range and standard `ATR(14)` are deterministic calculations over closed
daily candles. The initial ATR is the mean of the first 14 True Range values,
which requires 15 closed candles, and later values use Wilder smoothing. For
a trade date `D`, only candles before `D` contribute; if the provider cannot
return history before `D`, the context is stale or unavailable. Current-session
range remains separate and may be compared with ATR and the advisory 75%
reference.

The draft workspace also compares the exact planned price movement from entry
to take profit with the same reference:

```text
target_movement = abs(take_profit - entry)
target_atr_percent = target_movement / ATR(14) * 100
fits_reference = target_atr_percent <= 75
```

This comparison is advisory. It does not change the take profit, position
size, risk, or lifecycle validity.

Provider failure preserves no stored candles and simply marks the context
stale. When a trade leaves `DRAFT`, the available ATR value, contributing
date, ATR source and provider, current-session range, observation time, and
stale state are frozen with the other decision facts. Missing or stale market
context remains advisory and does not block the manual trade lifecycle.

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

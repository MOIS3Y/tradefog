# Tradefog domain model

## Ownership

All journal data belongs to one authenticated user. Public registration is not
part of the initial product; administrators create accounts. Every profile,
asset, pair, trade, snapshot, and attachment query is scoped by owner.

The custom user model derives from Django's `AbstractUser` so it can evolve
without a disruptive user-model migration later.

## Assets

`Asset` is an owner-scoped reusable catalog entry. It stores a normalized
symbol, an optional descriptive name, and a small asset class such as crypto,
equity, fiat, or other.

Symbols are unique for an owner without regard to letter case. Historical
identity remains stable after an asset is referenced. Archiving removes an
asset from normal new selections without deleting historical relations.

## Trading profiles

A `TradingProfile` represents one virtual risk-managed allocation. It is
deliberately independent from the topology and total balance of an exchange
account.

A profile stores:

- owner and name;
- execution provider;
- capital, quote, and settlement asset;
- market type;
- immutable initial capital after trading begins;
- risk percent per trade;
- mutable absolute risk-stop capital;
- operational status.

The initial execution provider is `MANUAL`. `BYBIT` appears only when a real
adapter exists. The provider is immutable. Capital asset and market type are
locked once the profile has a trading pair. Initial capital and risk percent
remain correctable while every trade is a draft and become locked after the
first trade is submitted.

One profile has one market type:

- `SPOT` supports `LONG` only;
- `LINEAR_PERPETUAL` supports `LONG` and `SHORT` with isolated margin at
  fixed `1x` in the initial strategy.

Separate Spot and Linear profiles have separate virtual capital, risk state,
and analytics, although a future exchange connection may serve both. The
first version excludes spot margin, configurable leverage, inverse contracts,
expiring futures, options, and contract multipliers.

## Capital operations

Users do not overwrite current capital. It is derived from recorded facts:

```text
current_capital =
    initial_capital
    + sum(deposits)
    - sum(withdrawals)
    + sum(realized_pnl)
```

Capital operations are explicit `DEPOSIT` or `WITHDRAWAL` records with an
amount, optional note, and automatic creation timestamp. They cannot be
backdated because they represent the moment the journal allocation changes.
They may be corrected when entered mistakenly.

A withdrawal cannot exceed positive current virtual capital. It may occur
while trades are open and may deliberately place the profile at or below its
risk stop. No capital operation instructs an exchange to move funds.

Deposits and withdrawals affect future position sizing and profile status but
not trading-quality analytics.

## Risk sizing

Future trade risk uses the greater of initial and current capital:

```text
risk_base = max(initial_capital, current_capital)
risk_amount = risk_base * risk_percent / 100
take_profit_amount = risk_amount * 3
```

Initial capital is therefore a floor for position-risk sizing. Losses below it
do not shrink subsequent planned monetary risk. Profits and additional
allocated capital above it increase planned risk proportionally.

The absolute `risk_stop_capital` is selected by the user. It identifies the
capital level at which trading should stop. It does not trail profit or change
automatically after deposits and withdrawals. A form may suggest 90% of
initial capital, but only the resulting absolute amount is persisted.

## Profile status

Profile status has four values:

- `ACTIVE`;
- `AT_RISK`;
- `RISK_STOPPED`;
- `ARCHIVED`.

Pending and open trades reserve their snapshotted planned risk:

```text
reserved_risk =
    sum(planned_risk_amount for PENDING_ENTRY and OPEN trades)

worst_case_capital = current_capital - reserved_risk
```

An archived profile always reports `ARCHIVED`. Otherwise it is
`RISK_STOPPED` when current capital is at or below the stop, `AT_RISK` when
current capital is above the stop but worst-case capital is at or below it,
and `ACTIVE` otherwise. Restoring an archived profile recalculates its
financial status.

Financial facts are the source of truth. Focused domain services update the
persisted operational status after relevant capital and trade transitions.

The risk stop is advisory for manually recorded activity. A draft can always
be saved. A manual or imported trade can be marked pending or open after a
clear warning, and the trade stores the breach fact. A future automatic
adapter does not send a new order that breaches the limit, but it still
imports externally placed violating trades.

## Profile trading pairs

`ProfileTradingPair` connects one base `Asset` to one profile. Its quote and
settlement asset is the profile's capital asset. The journal's canonical
display is always:

```text
BASE/QUOTE
```

Base and quote must be different. One active occurrence of a base asset may
exist in a profile. Price and quantity steps, precision, minimum quantity,
minimum notional, optional provider symbol, and market-data source
configuration belong to this profile-specific relation because venue rules
may differ.

The display separator is not profile configuration. A future adapter composes
its own external symbol from structured assets—for example, Bybit may use
`BTCUSDT` while the journal displays `BTC/USDT`. An exceptional provider can
store an explicit external symbol on the pair relation. Venue formatting does
not leak into the canonical journal identity.

Cross-currency conversion is outside profile risk sizing. It belongs to a
future cross-profile portfolio view if that feature becomes necessary.

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

Quantity is rounded down to the pair's quantity step so the resulting plan
does not exceed the snapshotted risk. Plans below minimum quantity or notional
are invalid or clearly marked. A Linear plan whose notional exceeds available
profile capital at `1x` is marked infeasible; leverage is never increased to
make it fit.

Financial, price, quantity, percentage, P&L, and R calculations use decimal
arithmetic with explicit rounding.

## Trade lifecycle

The initial lifecycle is:

- `DRAFT`;
- `PENDING_ENTRY`;
- `OPEN`;
- `CLOSED`;
- `CANCELLED`.

A draft is an analyzed setup that may never be traded and reserves no risk.
`PENDING_ENTRY` represents a placed but unfilled order and reserves planned
risk. `OPEN` reserves the same risk after entry. Cancelling an unfilled order
or closing a position releases the reservation and recalculates profile
status.

Lifecycle changes are coordinated by focused operations such as
`submit_trade`, `open_trade`, `cancel_trade`, and `close_trade`. These
operations form the shared boundary used by HTTP views now and exchange
adapters later.

When a trade leaves `DRAFT`, it snapshots enough decision context to remain
reproducible:

- planned risk percent and amount;
- reward multiple;
- current capital and risk base;
- risk-stop capital;
- already reserved risk;
- remaining risk capacity;
- risk-limit breach state;
- position-plan material values;
- eventually, the relevant ATR context.

Later capital operations, profile corrections, and other trades do not
rewrite these snapshots.

## Closing and realized result

The first version does not model partial fills or exits. A partially closed
position remains `OPEN`. Once fully closed, it stores one final signed net
`realized_pnl` in profile currency. This number is authoritative and already
includes fees, slippage, stops, targets, funding, and manual exits.

An optional actual exit price is reference data. Optional total commission
and signed funding result explain the net outcome but are not subtracted from
it again. Realized P&L changes current profile capital when closure is
registered in Tradefog.

A retrospectively entered trade belongs analytically to its `trade_date` but
changes current capital at registration time. Correcting journal facts
recalculates analytics and current profile state without rewriting snapshots
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

One internal signed score ranges from `SHORT` through neutral to `LONG`.
Unanswered weighted values add zero to the numerator while retaining their
possible weight in the denominator. Text, prices, and raw ATR do not
contribute to the directional score.

## Market snapshots and ATR

Market observations are scoped to a profile trading pair because provider,
market type, candles, and symbol rules vary. A dated closed daily candle stores
at least high, low, close, source identity, and trading date.

True Range and standard `ATR(14)` are deterministic calculations over closed
daily candles. Current-session range remains separate. Market-data source and
execution provider are independent concerns.

## Attachments

Screenshots and other trade attachments are private journal data. They are
associated with an owned trade and served only after an authenticated
ownership check. Public sharing is not part of the initial model.

# Tradefog product specification

## Purpose

Tradefog is a personal, self-hosted trading journal for a rules-based trading
process. Its purpose is to help a trader prepare, document, track, review, and
analyze discretionary trades while maintaining explicit risk discipline.

The journal and its virtual wallet are the primary product. Tradefog is not
an algorithmic trading platform, an exchange terminal, or a system that
claims to predict market outcomes. Market-data providers are optional aids;
they do not own balances, trades, or analytics.

The guiding idea is:

> You cannot control the market. You can control how much you risk.

## Product principles

Tradefog evaluates the quality and consistency of trading decisions across a
series of trades. Capital growth by itself is not evidence of good trading,
and checklist output is not a probability of profit.

The interface describes checklist results as a setup score, setup quality,
strategy alignment, or checklist assessment. It does not describe them as a
guaranteed result or expected win probability. The assessment is advisory and
can disagree with the trader's selected direction without blocking the trade.

The configured risk applies to each trade. There is no daily risk budget,
monthly accounting period, monthly target, or required trading frequency. A
small number of clean profitable decisions is more valuable than a larger
mixed sequence that produces the same normalized result.

The planned risk/reward ratio is fixed at `1:3`. It is a product strategy
constant rather than a user preference. The take-profit price is calculated
from entry and stop prices and cannot be edited independently.

Tradefog is an honest personal journal, not a regulatory audit system. Users
can correct dates and journal facts when they make a mistake. The application
recalculates affected analytics instead of maintaining an immutable audit
history.

## Primary workflow

The complete discretionary-trade workflow is:

1. The user creates a venue and configures its Spot, Linear Perpetual, or Cash
   Equity catalog manually or through a public instrument adapter.
2. The user creates a trading profile by choosing that venue and Crypto or
   Equity market class.
3. Inside the profile, the user enables compatible venue products and selects
   a working subset of venue instruments.
4. Every profile instrument selection defaults to a manual market-data feed;
   an automatic feed requires deliberate setup.
5. The user adds eligible assets exposed by selected instruments to the
   profile wallet and records virtual funds.
6. The user creates a trading strategy with one compatible wallet settlement
   asset and fixed risk parameters.
7. The user opens Trades and selects a profile and strategy.
8. The workspace filters products and instruments by exact strategy settlement;
   product determines the available `LONG` and `SHORT` directions.
9. The user completes the trade-specific checklist.
10. The directional assessment reacts to checklist changes.
11. The workspace presents the current ATR context for the instrument.
12. The user enters the planned entry and stop prices.
13. Tradefog calculates take profit, position quantity, and monetary risk.
14. The trade is saved as a draft or moved to a pending or open state.
15. An opened trade remains active until the entire position is closed.
16. Throughout the trade, the user maintains a Markdown description and
    private screenshots or supporting files in the same workspace.
17. The user records one final net realized P&L value and explicitly marks
    the review complete after adding any final errors and conclusions.
18. Strategy statistics and the quality trajectory include the closed trade.

Manual tracking is the only execution workflow. The user places and manages
orders outside Tradefog, then records their state and final result in the
journal. This supports every venue, including ones with no public API.

## First-use setup

First use is resumable rather than a disposable modal wizard. With no venue,
the empty home page directs the user to create one. A venue catalog is a
reusable prerequisite; after it exists, profile setup highlights the next
incomplete requirement:

```text
Create venue
    ↓
Add or synchronize venue products and instruments
    ↓
Create profile
    ↓
Select products and instruments
    ↓
Configure wallet
    ↓
Create strategy
    ↓
Create first trade
```

The profile form asks only for name, venue, and market class. Crypto then
offers the venue's Spot and Linear catalogs; Equity offers its Cash Equity
catalog. Profiles select instruments but never recreate their assets, symbols,
precision, or order rules.

A new venue defaults to manual instrument maintenance. Manual entry asks for
base, quote, and explicit settlement metadata and creates or reuses internal
venue assets automatically; there is no separate asset CRUD. Public
instrument adapters synchronize complete product catalogs when available.
Future authenticated execution connections are configured for a specific
profile product rather than as global user or venue credentials.

Venues are managed under Settings rather than inline during profile creation.
If no active venue exists, the profile form disables its venue selector and
save action and links to Settings → Venues.

After profile instruments are selected, the wallet screen presents their
unique eligible base, quote, and settlement assets as choices. The strategy
form then offers only the intersection of wallet assets and active instrument
settlements. Therefore a USD strategy cannot be created without an active
USD-settled profile instrument.

A profile is ready for drafts when it has an active instrument selection, a
compatible wallet asset, and a strategy. Positive available wallet funds are
required only for a transition to pending or open. Candle history and
automatic market data are optional advisory context and never block manual
journaling.

## Trade date

Every trade has an editable `trade_date`. It defaults to the current date in
the configured time zone and supports retrospective journal entries.

`trade_date` determines every time-filtered statistic. Execution and audit
timestamps such as creation, submission, fill, cancellation, and closing do
not move the trade to a different analytical period. A trade created for
August and closed in September remains part of August analytics.

There is no trading-day object or required daily session. Daily statistics
are derived from individual trade dates.

## Trade workspace

The trade editor is one cohesive workspace rather than a multi-step wizard.
It combines:

- pair and direction selection;
- checklist and setup assessment;
- ATR context;
- planned entry, stop, take profit, and position size;
- lifecycle actions;
- an evolving trade description, private attachments, and final review.

Creating a trade selects profile, strategy, product, and pair before using the
rest of the cohesive workspace. Product is a filtering step and is derived
from the final pair rather than duplicated on the trade. Pair choices belong
to the position section and exactly match the strategy settlement asset. An
empty draft is not persisted merely because context was selected; an explicit
save or lifecycle action creates it.

Several separately recorded entries for the same pair and direction are
separate journal decisions. The first version has no position group, setup
group, or trade batch abstraction.

The trade description is available in every lifecycle state and remains in
the trade workspace after the checklist. It stores Markdown edited through an
inline toolbar-enhanced textarea. Images and other files are separate private
attachments rather than embedded remote resources in the Markdown document.
Only a closed trade can be explicitly marked as reviewed. Review completion
is independent of the trade lifecycle and remains an editable journal fact.

## Checklist and setup assessment

All trades use one application-defined directional checklist. Its fields and
weights are not user-configurable in the initial product. It records four
observations that remain meaningful across market types:

| Observation | Interpretation | Weight |
| --- | --- | ---: |
| Broad market sentiment | Bearish, neutral, or bullish behavior in the relevant market or sector | 1 |
| Information background | Negative, neutral, or positive news, media, regulatory, and legal context | 1 |
| Global D1 direction | Down, sideways, or up over approximately 20–30 daily candles | 3 |
| Local D1 movement | Down, sideways, or up over approximately 5–7 daily candles | 2 |

The global and local D1 relationship is derived from their answers rather
than entered or weighted separately. ATR is separate non-directional context.
Entry patterns, levels, volume, order-book observations, and post-trade review
are not part of this universal directional assessment.

Weighted answers produce one signed directional assessment from `SHORT`
through neutral to `LONG`. Unanswered questions contribute zero while their
possible weight remains in the denominator, keeping an incomplete checklist
near neutral. Completeness is shown separately.

The user-facing gauge emphasizes marker position, color, and directional text
instead of presenting a misleading percentage. ATR is shown separately
because volatility is not direction.

A future owner-defined strategy checklist may assess how strongly a setup
matches a particular trading method. That assessment is distinct from market
direction, requires versioned criteria, and is not part of the fixed initial
checklist.

## ATR context

The initial indicator is standard daily `ATR(14)` based on True Range. The
observation that an instrument commonly travels approximately 75% of its
daily ATR is presented only as soft context about remaining movement. It is
not a reversal probability or a hard rule.

Market data is loaded on demand when a pair is selected in the trade
workspace. A refresh action supports long-lived drafts. This design avoids a
scheduler or background daemon. Cached data remains usable when an external
source is temporarily unavailable and is visibly marked stale.

Each profile instrument selection has one active daily-candle feed and
defaults to manual maintenance. Automatic Bybit or Twelve Data feeds are
enabled explicitly and remain independent from venue catalog synchronization
and execution. Manual candles are editable; automatic candles are read-only
provider cache. Tradefog calculates ATR locally regardless of candle source.

For a trade date `D`, ATR uses only candles dated before `D`. A still-forming
Bybit candle dated `D` supplies the separate observed-session range. A
completed historical range is not presented as if it had been observable at
decision time. The workspace also plots the last 14 closed candles before
`D` as a compact candlestick chart; it never includes `D` or later candles.
Calculated ATR values are displayed at the pair's configured price-step
precision without reducing calculation precision. Exact candle values remain
available in the chart without thousands grouping or display rounding. The
workspace separately shows whether the planned entry-to-take-profit price
movement fits within 75% of ATR. This comparison is advisory and reacts to
draft plan edits. The ATR context used for a submitted trade is snapshotted so
later candle corrections or trade-date corrections do not rewrite the
original decision context.

## Analytics

The core measure of trading quality is the sequence of normalized closed
trade results. Important statistics include:

- total, profitable, losing, and break-even trades;
- win rate;
- net and average result in R;
- gross profit and gross loss in R;
- net realized P&L in strategy currency;
- current and maximum winning or losing streaks;
- drawdown from the historical capital high where appropriate;
- the X/Y quality trajectory;
- checklist values and assessment;
- strategy compliance, errors, and conclusions.

Analytics supports lifetime results, common rolling ranges, and arbitrary
`date_from`/`date_to` ranges. Every filtered trajectory starts at `(0, 0)` and
is recalculated from trades selected by `trade_date`. It does not continue
from a lifetime coordinate.

Wallet deposits and withdrawals never enter the quality trajectory. Monetary
P&L is displayed in its settlement asset; results in unlike assets are never
summed without an explicit conversion policy.

Future comparisons may group results by setup score, checklist criterion,
trading pair, asset, direction, provider, date range, strategy compliance, or
error type. Such correlations are analytical observations and do not prove a
stable trading edge.

## Navigation and information architecture

The authenticated application uses a sticky two-row horizontal shell. The
upper row holds the brand, theme control, and user menu; the second row holds
the main navigation:

```text
Home
Profiles
Trades
Analytics
Settings
User menu
  Settings (future user settings; disabled placeholder)
  Log out
```

- Home shows the first-use action or a restrained cross-profile overview with
  drafts and positions that need attention.
- Profiles is the configuration root. Each profile contains Overview,
  Instruments, Wallet, Strategies, Trades, and Settings.
- A profile wallet contains balances, manual deposits and withdrawals,
  reservations, available funds, and activity.
- Settings → Venues owns reusable Spot, Linear, and Cash Equity instrument
  catalogs. Manual venues allow instrument maintenance there; adapter-backed
  venues synchronize their public catalogs there.
- A profile's Instruments page selects and archives its working subset from
  the chosen venue catalog. There is no standalone asset screen.
- Trades contains the cross-profile journal, owner-scoped profile, strategy,
  product, pair, and lifecycle filters, server-ordered paginated results,
  trade creation, and the trade workspace.
- Analytics contains lifetime and filtered quality trajectories and
  comparisons.

Profile pages do not duplicate the trade editor. They may link to filtered
trades or analytics. Trades is a real top-level section rather than a hidden
profile selector.

All user-facing routes have an explicit language prefix. Representative URLs
are:

```text
/en/
/en/profiles/
/en/profiles/<id>/
/en/profiles/<id>/instruments/
/en/profiles/<id>/wallet/
/en/profiles/<id>/strategies/
/en/settings/venues/
/en/settings/venues/<id>/instruments/
/en/trades/
/en/trades/new/
/en/trades/<id>/
/en/analytics/
```

The root route remains available for the cross-profile home page, so the
application does not use a redundant `/journal/` prefix.

## Deferred product capabilities

The following capabilities remain optional until the manual journal is
useful and stable:

- authenticated exchange execution and synchronization;
- TradingView Advanced Chart embedding;
- cross-profile portfolio conversion;
- additional market types;
- partial-fill and partial-exit modeling;
- notifications and scheduled background work.

TradingView embedding, if added, is an opt-in visual aid with attribution. It
is not a market-data API and does not supply ATR calculations.

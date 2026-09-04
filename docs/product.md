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

The planned risk/reward ratio comes from the strategy (the default is `1:3`)
rather than being a per-trade user preference. The take-profit price is
calculated from entry and stop prices and cannot be edited independently.

Tradefog is an honest personal journal, not a regulatory audit system. Users
can correct dates and journal facts when they make a mistake. The application
recalculates affected analytics instead of maintaining an immutable audit
history.

## Primary workflow

The complete discretionary-trade workflow is:

1. A staff member maintains the shared reference catalog: assets, trading
   pairs, venues, and venue instruments, plus which assets settle a wallet on
   each venue. Regular users never create or edit catalog records; they ask a
   staff member when they need a new market.
2. The user creates a trading profile and binds it to one venue.
3. The user opens the profile wallet, adds venue-capable assets offered by
   that venue, and records deposits and withdrawals.
4. The user creates a trading strategy: sets the risk percent and reward
   multiple, and allocates a fixed capital to each available wallet asset the
   strategy will trade against. One strategy is reused across all its
   allocated assets.
5. The user opens Trades and selects a profile and strategy.
6. The workspace filters instruments by the strategy's allocated settlement
   assets and the profile's venue; product determines the available `LONG`
   and `SHORT` directions.
7. The user completes the trade-specific checklist.
8. The directional assessment reacts to checklist changes.
9. The workspace presents the current ATR context for the instrument; the user
   picks a data source and refreshes it on demand.
10. The user enters the planned entry and stop prices.
11. Tradefog calculates take profit, position quantity, and monetary risk.
12. The trade is saved as a draft or moved to a pending or open state.
13. An opened trade remains active until the entire position is closed.
14. Throughout the trade, the user maintains a Markdown description and
    private screenshots or supporting files in the same workspace.
15. The user records one final net realized P&L value and explicitly marks
    the review complete after adding any final errors and conclusions.
16. Strategy statistics and the quality trajectory include the closed trade.

Manual tracking is the only execution workflow. The user places and manages
orders outside Tradefog, then records their state and final result in the
journal. This supports every venue, including ones with no public API.

## First-use setup

First use is resumable rather than a disposable modal wizard. For a regular
user the journal has no venue or instrument creation; the shared catalog
already exists and is maintained by staff. If the catalog is empty, the empty
home page directs the user to contact a staff member. Profile setup highlights
the next incomplete requirement:

```text
Create profile
    ↓
Configure wallet
    ↓
Create strategy
    ↓
Create first trade
```

The profile form asks for a name and the venue it is bound to. The market
family is derived from the product of the instrument the user eventually
trades; the profile does not ask for a market class. Users never recreate
assets, symbols, precision, or order rules — those live once in the shared
catalog.

A regular user can read and use any shared instrument but cannot create or
edit catalog records. A user who needs a new asset, pair, venue, or venue
instrument asks a staff member to add it. Staff members manage the catalog
under Settings rather than inline during profile creation.

The wallet belongs to one profile and is bound to that profile's venue. Its
screen presents only the assets that are wallet-capable on that venue
(`VenueWalletAsset`) as choices; the user records deposits and withdrawals
against them. The strategy form then offers only the intersection of wallet
assets and instrument settlements. Therefore a USD strategy cannot be created
without an active USD-settled instrument on the profile's venue.

A profile is ready for drafts when it has a wallet asset and a strategy.
Positive available wallet funds are required only for a transition to pending
or open. Market data is optional advisory context and never blocks manual
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

A logical pair such as BTC/USDT can exist on one venue as several distinct
executable instruments distinguished by product, for example a Spot and a
Perpetual Future. To avoid an ambiguous pair selector, the workspace asks for
the product first as a two-step choice:

```text
profile → product (Spot | Perpetual Future | Cash Equity) → pair
```

The product selector offers only products that have at least one instrument on
the profile's venue. The pair selector then lists only the instruments of the
chosen product; each option is a concrete venue instrument shown by its
canonical pair and product tag, never a bare logical pair. Product determines
the available directions: Spot and Cash Equity allow `LONG`, Perpetual Future
allows `LONG` and `SHORT`.

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
scheduler or background daemon. Candles are never stored in the database;
they are a transient request result, so there is no stale cache or history to
clean up. Only the resulting ATR decision snapshot is saved on a submitted
trade.

When the instrument has a provider source, the user selects Bybit or Twelve
Data and refreshes it in the workspace. When it has no provider source, the
user may enter the ATR value manually as the `MANUAL` source. An instrument
with no source and no entered value reports ATR as `N/A`. Tradefog calculates
ATR locally for `AUTO` sources regardless of provider.

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
later refreshes or trade-date corrections do not rewrite the original decision
context.

## Analytics

The core measure of trading quality is the sequence of normalized closed
trade results. Important statistics include:

- total, profitable, losing, and break-even trades;
- win rate;
- net and average result in R;
- gross profit and gross loss in R;
- net realized P&L per settlement asset;
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
Catalog
  Assets
  Trading pairs
  Venues
User menu
  Settings (future user settings; disabled placeholder)
  Log out
```

- Home shows the first-use action or a restrained cross-profile overview with
  drafts and positions that need attention.
- Profiles is the configuration root. Each profile contains Overview, Wallet,
  Strategies, Trades, and Settings. The overview is an owner-scoped card grid:
  active profiles sit in the main grid, and archived profiles are listed below
  under an Archives heading that appears only when at least one profile is
  archived. A profile is archived through a confirmation modal and restored
  directly from its card. Archiving keeps the wallet, strategies, and trade
  history intact but hides the profile from new trades and analytics until it
  is restored; only an archived profile can be deleted permanently.
- A profile wallet contains balances, manual deposits and withdrawals,
  reservations, available funds, and activity.
- Settings → Catalog (staff only) owns the shared assets, trading pairs,
  venues, and venue instruments. Regular users read this catalog but cannot
  create or edit it; they ask a staff member for new markets.
- Catalog is a staff-managed area that lists the shared reference catalog.
  Its Assets page supports search, type filtering, sorting, and pagination;
  regular users read it, while staff create and remove assets through modal
  forms with dismissible status alerts.
- Trading pairs lists the reusable BASE/QUOTE markets with search, a dynamic
  base/quote asset-type filter, sorting, and pagination; regular users read
  it, while staff create and remove pairs through modal forms with
  dismissible status alerts. A Filters button above the results reveals the
  filter panel, which is collapsed by default and stays open while its
  filters are applied.
- Venues lists the shared exchanges and execution destinations as a small
  responsive card grid with instrument and wallet-asset counts; regular users
  read it, while staff create and remove venues through modal forms. A venue
  detail page presents the venue through three card tabs: Instruments (the
  executable markets with filters, sorting, a settlement column, and a read-only
  details modal open to every user), Wallet assets (the venue-capable assets),
  and Settings (the venue name and website). A Filters button beside the add
  action reveals each collection's filter panel. Staff manage instruments and
  wallet assets through modal forms, delist instruments with an inline switch,
  and edit the venue name and website on the Settings tab; regular users read
  every tab and inspect instrument parameters, with Settings shown read-only.
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
/en/profiles/<id>/wallet/
/en/profiles/<id>/strategies/
/en/catalog/assets/
/en/catalog/pairs/
/en/catalog/venues/
/en/catalog/venues/<id>/
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

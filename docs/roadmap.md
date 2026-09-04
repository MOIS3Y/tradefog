# Tradefog roadmap

Development proceeds in small, reviewable stages. Each stage is implemented,
tested, reviewed manually, and committed before the next stage begins.

## Completed foundation

### Stage 1: identity and ownership

- custom Django user model;
- administrator-created accounts without public registration;
- localized login and logout;
- authenticated application shell;
- locally vendored Tabler UI;
- focused authentication and routing tests.

### Stage 2: initial profiles and markets

- owner-scoped profile creation, editing, archiving, and restoration;
- the initial manual provider and market representation;
- profile overview and workspace;
- two-level Tabler navigation shell;
- English and Russian interface coverage.

The original profile-instrument representation was intentionally superseded
by Stage 4 while pre-release compatibility was inexpensive.

### Stage 3: profile capital and risk state

- profiles based on initial capital, risk per trade, and an absolute risk
  stop;
- explicit deposit and withdrawal operations;
- capital derived from facts rather than an editable balance;
- `ACTIVE`, `AT_RISK`, `RISK_STOPPED`, and `ARCHIVED` states;
- profile configuration, capital controls, and status presentation;
- removal of the abandoned accounting-period design.

### Stage 4: assets, pairs, and manual trades

- owner-scoped reusable asset catalog;
- capital asset and homogeneous market type on each profile;
- profile-scoped trading pairs with precision and minimum-order rules;
- Spot LONG-only and isolated `1x` Perpetual Future LONG/SHORT behavior;
- cross-profile Trades section and two-step trade creation flow;
- editable analytical trade dates;
- deterministic `1:3` position sizing;
- draft, pending, open, closed, and cancelled lifecycle;
- pending/open risk reservation and profile status updates;
- decision-time risk snapshots and advisory breaches;
- net realized P&L, optional commission, and signed funding context;
- focused ownership, validation, lifecycle, calculation, and UI tests.

### Stage 5: core X/Y analytics

- pure lifetime and date-filtered trajectory calculations;
- all-time, common rolling-range, and arbitrary date filters;
- a trajectory recalculated from `(0, 0)` using `trade_date`;
- the `Y = X / 3` break-even line without an artificial target line;
- net and average R, outcome counts, win rate, and streaks;
- profile, pair, market-type, and date filtering where useful;
- a locally vendored ApexCharts visualization styled with Tabler UI;
- HTMX filtering with stable query-string URLs;
- a functional Analytics navigation item;
- coverage for partial outcomes, ordering, filters, and corrections.

Capital operations and capital size remain outside these quality metrics.

### Stage 6: checklist and directional assessment

- a fixed cross-market checklist with explicit `1/1/3/2` weights;
- typed, versioned answers attached one-to-one to each saved trade;
- pure signed scoring, completeness, and derived D1 relationships;
- atomic draft and checklist persistence with read-only submitted context;
- an advisory `SHORT`-to-`LONG` gauge in the HTMX trade workspace;
- preserved disagreement between selected direction and checklist assessment;
- English and Russian segmented controls and read-only presentation;
- focused calculation, lifecycle, ownership, HTMX, and UI coverage.

User-defined strategy checklists remain a separate future capability because
they measure setup strength and require immutable strategy versions.

### Stage 7: on-demand market data and ATR

- profile-pair candle sources defaulting to manual maintenance;
- owner-scoped closed daily OHLC maintenance and provenance;
- deterministic True Range and Wilder `ATR(14)` calculations before the
  selected trade date;
- a separate cached current-session range and advisory 75% ATR reference;
- a public Bybit Spot/Perpetual Future daily-candle client using HTTPX;
- reactive pair/date loading and explicit draft refresh;
- a date-safe two-week candlestick chart using the vendored ApexCharts;
- a cross-profile pair registry with direct pair and candle-management
  actions;
- consistent pair and candle filters with server-side sorting and paginated
  HTMX results;
- consistent server-side sorting and pagination for assets, trades, profile
  pairs, archived pairs, and capital history, plus operational trade filters;
- a global progressively revealed back-to-top control for long histories;
- cached fallback with visible stale state after provider failure;
- immutable ATR decision snapshots when trades leave draft;
- English and Russian server-rendered presentation and focused coverage.

Market data remains independent of execution providers, and unavailable ATR
does not block the manual journal workflow.

### Stage 8: post-trade review and private attachments

- an evolving Markdown trade description for observations, errors, and
  conclusions in every lifecycle state;
- private screenshots and other trade attachments;
- asynchronous per-file uploads with visible progress and an image lightbox;
- owner-checked authenticated attachment delivery;
- visible incomplete review without another complex lifecycle state.

## Completed restructuring

### Stage 9: account-scoped wallet and strategic-profile restructuring

- owner-activated Crypto and Equities markets, venues, and market-specific
  trading accounts;
- account-wallet assets with account-specific balances, reservations,
  deposits, withdrawals, and trade-result effects;
- strategic profiles with fixed capital, fixed monetary risk, virtual equity,
  one settlement wallet asset, and no profile capital operations;
- venue-specific pairs whose product determines directions and which are
  automatically available to compatible account profiles;
- wallet-backed `1x` notional validation for pending and open trades;
- global market candle sources and cached local candle history;
- Crypto Spot, Crypto Perpetual Future, and Equity Cash product rules;
- sticky horizontal navigation shell, wallet page, grouped profile navigation,
  market catalog, user settings, and footer;
- a structural reorganization of journal models, forms, services, views, and
  templates into cohesive subpackages;
- replacement of pre-release migrations and development/test databases.

## Planned stages

### Stage 10: shared reference catalog and direct instrument reference

Replace the market activations, trading accounts, global owner assets, global
pairs, `ProfileAsset`, and profile-owned pair duplication with a shared,
staff-managed reference catalog that regular users read but do not edit:

- introduce a shared `Asset` with a globally reusable symbol and an
  unambiguous Crypto, Equity, or Fiat type, and a reusable `TradingPair` as
  the logical `BASE/QUOTE` market;
- introduce shared `Venue`, `VenueInstrument`, and `VenueWalletAsset`
  records, with product kind Spot, Perpetual Future, or Cash Equity placed on
  the instrument so the market class is derived and a venue can host several
  products without duplication;
- make only staff members create or edit catalog records; regular users read
  and reuse them and request new markets from staff;
- drop the `ProfileProduct`/`ProfileInstrument` working-subset selection
  layer and the venue-scoped `VenueAsset`; trades reference a shared
  `VenueInstrument` directly;
- keep `TradingProfile` as the owner-scoped journal context bound to one venue
  and owning a one-to-one `Wallet`, strategies, and trades, with
  `TradingProfile.owner` as the single ownership root and all journal queries
  routed through a centralized scoping manager;
- make `WalletAsset` reference `VenueWalletAsset` so profile wallet assets are
  venue-capable on the profile's venue;
- keep `TradingStrategy` as the profile-scoped edge layer (risk percent and
  reward multiple) backed by `StrategyCapital` per-asset allocations, so one
  strategy is reused across every wallet asset it allocates and the fixed
  allocation capital is never resized; the advisory `risk_stop_capital`
  deposit floor lives on `WalletAsset`;
- introduce a write-once `TradeSnapshot` created atomically on the
  draft-to-pending transition, freezing the plan, risk, wallet, and ATR
  context and backing the derived wallet reservation while the trade is
  pending or open;
- enforce shared-catalog, product, and exact-settlement compatibility in
  selectors, draft persistence, and every pending or open transition;
- stop persisting market data: remove candle tables and feeds, fetch the last
  closed daily candles on demand in the trade workspace, and store only an
  ATR decision snapshot (`AUTO` or `MANUAL` source) on submitted trades;
- reshape Settings → Catalog for staff management and the trade workspace for
  direct instrument selection and on-demand data refresh;
- update first-use setup, trade flow, analytics terminology, ownership zones,
  English and Russian UI, and focused regression coverage;
- replace obsolete pre-release migrations and local development or test
  databases rather than migrate their data.

Catalog collection pages for Assets and Trading pairs are implemented first:
each lists the shared records with server-side search, filtering, sorting,
and pagination, while staff create and remove records through modal forms.
The remaining venue, instrument, wallet, and trade-reference restructuring
continues in this stage.

Stage 9 remains implementation history. The revised Stage 10 supersedes its
account/catalog model, the interim profile-owned asset and pair model, and the
venue-scoped `VenueAsset`/selection-layer model.

### Stage 11: manual-journal hardening and release

- complete English and Russian translations;
- ownership, lifecycle, attachment, and HTMX regression coverage;
- SQLite, wheel, Nix package, and container verification;
- accessibility, responsive layout, empty-state, and validation review.

## Later roadmap

The following work begins only after the manual journal is useful and stable:

- authenticated exchange execution only after a concrete workflow justifies
  its independent complexity;
- automated order placement on selected venues (initially Bybit) as an
  additive v0.2.0 extension: owner-scoped named API keys selected by a
  profile, one-shot order placement without background execution tracking,
  and no effect on past trades or the manual journal;
- additional market-data providers beyond Bybit and Twelve Data;
- optional TradingView embedded chart as a clearly external visual aid;
- cross-profile portfolio views after currency-conversion requirements are
  known;
- advanced comparative analytics, drawdown, and checklist correlations;
- new market types or partial-execution modeling based on actual workflows.

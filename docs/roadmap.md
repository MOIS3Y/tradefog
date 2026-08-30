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
- Spot LONG-only and isolated `1x` Linear LONG/SHORT behavior;
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

## Planned stages

### Stage 6: checklist and directional assessment

- finalize the fixed checklist questions and weights;
- add the typed checklist model and form;
- implement pure signed directional scoring and completeness;
- integrate an advisory gauge into the HTMX trade workspace;
- preserve disagreement between selected direction and checklist assessment
  without blocking the trade.

### Stage 7: on-demand market data and ATR

- dated closed daily candles scoped to each profile trading pair;
- deterministic True Range and standard `ATR(14)` calculations;
- separate current-session range context;
- manual candle maintenance;
- the first public Bybit Spot/Linear candle source behind a focused boundary;
- reactive loading when a pair is selected and explicit refresh for old
  drafts;
- cached fallback and visible stale state after provider failure;
- an ATR decision snapshot when a trade leaves draft;
- advisory presentation of the observed 75% daily range.

This stage does not add a scheduler, daemon, task queue, Redis, or Celery.

### Stage 8: post-trade review and private attachments

- post-trade notes, errors, and conclusions;
- private screenshots and other trade attachments;
- owner-checked authenticated attachment delivery;
- visible incomplete review without another complex lifecycle state.

### Stage 9: manual-journal hardening and release

- complete English and Russian translations;
- ownership, lifecycle, attachment, and HTMX regression coverage;
- SQLite, wheel, Nix package, and container verification;
- accessibility, responsive layout, empty-state, and validation review.

## Later roadmap

The following work begins only after the manual journal is useful and stable:

- first concrete Bybit connection and execution adapter;
- entry, stop, and take-profit submission from the common workspace;
- exchange state and final P&L synchronization;
- additional market-data providers for equities and other asset classes;
- optional TradingView embedded chart;
- cross-profile portfolio views after currency-conversion requirements are
  known;
- advanced comparative analytics, drawdown, and checklist correlations;
- new market types or partial-execution modeling based on actual workflows.

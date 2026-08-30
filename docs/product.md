# Tradefog product specification

## Purpose

Tradefog is a personal, self-hosted trading journal for a rules-based trading
process. Its purpose is to help a trader prepare, document, track, review, and
analyze discretionary trades while maintaining explicit risk discipline.

The journal is the primary product. Exchange execution, notifications,
external APIs, and other integrations are secondary capabilities. Tradefog is
not an algorithmic trading platform, an exchange terminal, or a system that
claims to predict market outcomes.

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

1. The user authenticates and opens the application.
2. The user opens Trades and selects a trading profile.
3. The trade workspace receives a trading pair and a direction.
4. The user completes the trade-specific checklist.
5. The directional assessment reacts to checklist changes.
6. The workspace presents the current ATR context for the pair.
7. The user enters the planned entry and stop prices.
8. Tradefog calculates take profit, position quantity, and monetary risk.
9. The trade is saved as a draft or moved to a pending or open state.
10. An opened trade remains active until the entire position is closed.
11. The user records one final net realized P&L value.
12. The user adds post-trade notes, screenshots, errors, and conclusions.
13. Profile statistics and the quality trajectory include the closed trade.

Manual tracking is a first-class workflow. It supports exchanges without an
API and remains available after automated adapters are introduced. For a
manual profile, the user places and manages the order outside Tradefog and
records its state and result in the journal.

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
- post-trade review.

Creating a trade has only two conceptual steps: selecting a profile and using
the workspace. Pair selection belongs to the position section rather than a
separate page. An empty draft is not persisted merely because a profile was
selected; an explicit save or lifecycle action creates it.

Several separately recorded entries for the same pair and direction are
separate journal decisions. The first version has no position group, setup
group, or trade batch abstraction.

## Checklist and setup assessment

All profiles and markets use one application-defined checklist. Its fields
and weights are not user-configurable in the initial product. The exact field
set is intentionally scheduled for a focused implementation stage.

The current checklist concept covers:

- premarket and broad market context;
- global and local trend;
- agreement between timeframes;
- structural boundaries and important levels;
- ATR and remaining daily movement;
- momentum and price action;
- order-book or market-trade observations;
- planned entry and exit points;
- position management;
- post-trade description and review.

Weighted answers produce one signed directional assessment from `SHORT`
through neutral to `LONG`. Unanswered questions contribute zero while their
possible weight remains in the denominator, keeping an incomplete checklist
near neutral. Completeness is shown separately.

The user-facing gauge emphasizes marker position, color, and directional text
instead of presenting a misleading percentage. ATR is shown separately
because volatility is not direction.

## ATR context

The initial indicator is standard daily `ATR(14)` based on True Range. The
observation that an instrument commonly travels approximately 75% of its
daily ATR is presented only as soft context about remaining movement. It is
not a reversal probability or a hard rule.

Market data is loaded on demand when a pair is selected in the trade
workspace. A refresh action supports long-lived drafts. This design avoids a
scheduler or background daemon. Cached data remains usable when an external
source is temporarily unavailable and is visibly marked stale.

The first maintainable source is manual daily candle data. A public Bybit
Spot/Linear candle source is planned behind the same market-data boundary.
The ATR context used for a submitted trade is snapshotted so later candle
corrections do not rewrite the original decision context.

## Analytics

The core measure of trading quality is the sequence of normalized closed
trade results. Important statistics include:

- total, profitable, losing, and break-even trades;
- win rate;
- net and average result in R;
- gross profit and gross loss in R;
- net realized P&L in profile currency;
- current and maximum winning or losing streaks;
- drawdown from the historical capital high where appropriate;
- the X/Y quality trajectory;
- checklist values and assessment;
- strategy compliance, errors, and conclusions.

Analytics supports lifetime results, common rolling ranges, and arbitrary
`date_from`/`date_to` ranges. Every filtered trajectory starts at `(0, 0)` and
is recalculated from trades selected by `trade_date`. It does not continue
from a lifetime coordinate.

Deposits, withdrawals, and capital size never enter the quality trajectory.
When capital change is displayed, it is identified as change from the initial
allocation rather than as a cash-flow-adjusted investment return.

Future comparisons may group results by setup score, checklist criterion,
trading pair, asset, direction, provider, date range, strategy compliance, or
error type. Such correlations are analytical observations and do not prove a
stable trading edge.

## Navigation and information architecture

The main navigation is:

```text
Home | Profiles | Assets | Trades | Analytics
```

- Home is the future cross-profile summary with useful widgets.
- Profiles contains profile parameters, capital operations, status, and
  profile-specific trading pairs.
- Assets contains the owner's reusable catalog of base and capital assets.
- Trades contains the cross-profile journal, filters, trade creation, and the
  trade workspace.
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
/en/assets/
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

- exchange execution and synchronization;
- TradingView Advanced Chart embedding;
- cross-profile portfolio conversion;
- additional market types;
- partial-fill and partial-exit modeling;
- notifications and scheduled background work.

TradingView embedding, if added, is an opt-in visual aid with attribution. It
is not a market-data API and does not supply ATR calculations.

# Product Specification

## Purpose & Principles

Tradefog is a personal, self-hosted risk-discipline system and trading journal.
It does not predict price direction. It makes discretionary trading systematic
by fixing the acceptable loss before execution, deriving the reward target from
that loss, and showing when a sequence of decisions stops producing positive
expectancy.

> You cannot control the market. You can control how much you risk.

### Core Principles

1. **Risk-First Discipline**: Risk (1R) is derived from strategy rules and
   allocated capital, not arbitrary per-trade guesswork. Take profit is
   calculated deterministically from the strategy reward multiple.
2. **Positive Expectancy by Design**: Every strategy uses the canonical
   `1:N` risk-to-reward form, where `N` is a whole number from `3` through
   `100`. The minimum `1:3` target lets one full win cover three full losses;
   larger targets remain available for strategies with longer horizons.
3. **Quality Over Quantity**: Capital growth alone is not proof of skill.
   Tradefog tracks normalized performance (R-multiples), sample size, and
   decision quality so an efficient short sequence is not confused with a
   statistically reliable one.
4. **Advisory Assistance**: Checklist scores and ATR contexts provide advisory
   guidance without artificially blocking discretionary trades.
5. **Honest Self-Journaling**: Fast corrections of notes and review facts are
   supported with automatic analytics recalculation.

## User Workflow

1. **Profile Market Setup**: Each user chooses Bybit or manual. Bybit imports
   selected instrument specifications and assets; manual users enter them.
2. **Profile & Wallet Setup**: The user creates a `TradingProfile` with a fixed
   integration type, adds instruments or profile assets, and records
   deposits.
3. **Strategy Definition**: The user defines a `TradingStrategy` with a decimal
   risk percent (e.g. `5.5%`) and a whole reward multiple (e.g. `3` for
   `1:3`), allocating fixed capital from wallet assets. The percentage defines
   the monetary `1R`; it is not the left side of the ratio, which is always
   normalized to one.
4. **Trade Preparation (Workspace)**:
   - Works in the active profile and selects Strategy, Product, and Instrument.
   - Fills the 4-step directional checklist.
   - Refreshes on-demand ATR context.
   - Enters planned entry and stop loss. System computes take profit, position
     size, and 1R monetary risk.
5. **Trade Execution**:
   - Saves as `DRAFT` or transitions to `PENDING` / `OPEN` (freezing a
     `TradeSnapshot` and reserving wallet capital).
   - Keeps the frozen plan immutable after submission while notes, attachments,
     and the optional quality rating remain editable.
   - Manages external execution manually.
6. **Trade Closure & Review**:
   - Records final net realized P&L, closing date, and fees.
   - Documents observations, errors, and lessons in the Markdown workspace
     with optional private image attachments.
   - Optionally rates decision quality from 1 through 10. A five-star control
     may present the scale visually, with each full star representing two
     points and half-stars preserving odd scores.
   - Marks the trade as reviewed.

## First-Use Setup Flow

```text
Create Profile ──► Configure Wallet ──► Create Strategy ──► Create First Trade
```

- Profiles require a name and integration type (`bybit` or `manual`).
- Wallets show profile assets; balances are always virtual and explicitly funded.
- Strategies require at least one allocated wallet asset with positive balance.

## Trade Workspace Requirements

The working journal opens at `/profiles/{profile_id}/trades` as a paginated,
responsive table. `/trades` provides a read-only overview across profiles.
Rows show
date, instrument/direction, profile, strategy, lifecycle status, net P&L with
its currency, a read-only five-star quality rating, and review completion.
Half-stars preserve the 1–10 scale; empty stars mean no rating, never zero.
Review completion is independent of rating. The awaiting-review queue contains
only closed trades without a completion mark.

Search, filters and sorting run on the server before pagination. Date presets,
custom ranges, profile, strategy, direction, lifecycle, review and rating
filters live in the URL together with page and ordering. Returning from a
trade restores that list context. Unrated records sort last in both directions.

A side drawer in a profile's journal creates a draft, then opens
`/profiles/{profile_id}/trades/{id}`. Creation inherits the active profile and
asks for strategy, instrument and date; direction starts
as Long and is changed in the trade workspace. Closing the drawer preserves
list filters. The aggregate journal asks users to choose a profile before
creating a trade.
The individual trade page loads its full record independently and provides
the full lifecycle:

1. **Context Selector**: Strategy, Product (`SPOT`, `PERPETUAL_FUTURE`,
   `CASH_EQUITY`), and Instrument.
2. **Directional Checklist**: 4 questions evaluated on a `-1.0` to `+1.0` scale
   with visual advisory indicator.
3. **Market Volatility (ATR)**: On-demand daily `ATR(14)` calculation with
   recent candlestick preview; checks if planned move fits within 75% ATR.
4. **Position Calculator**: Deterministic position sizing based on entry, stop,
   and 1R risk amount.
5. **Notes & Attachments**: Markdown notes editor with secure private file
   uploads.
6. **Review Stage**: Post-trade error tagging and reflective conclusions.

ATR is advisory evidence, not a direction or probability forecast. It shows
whether the planned target is unusually large relative to recent daily range.

## Profile-owned Refactor Delivery

The persistent navigation selector chooses a profile or All profiles. Profile
routes own trades, analytics, market setup, wallets and strategies; `/profiles`
manages profile records. Switching profiles retains the section and common
filters, but clears resource selections, search and pagination. Switching from
a trade opens the destination profile's list. All profiles retains aggregate
trades and analytics; opening a trade enters its profile and preserves the
return URL.

The URL is authoritative and each browser tab has its own working context.
The normal entry point restores the last context stored for that user; a first
visit opens aggregate trades. An unavailable saved profile falls back to the
overview, while an unavailable direct link shows a not-found state. Archived
profiles remain selectable with the existing domain restrictions. Navigation
protects unsaved forms and waits for submitted mutations to finish.

The profile-owned API and SPA are implemented. Each profile provides Venue,
Wallet and Strategies sections. Bybit imports only selected instruments and
their required assets; manual profiles create both locally. Global catalog
screens have been removed. The server supplies public Bybit metadata, candles
and depth without depending on chart rendering; the browser never calls the
exchange directly. Market failures do not disable journal controls.

Cash instruments support purchase/resale and owned-asset sale/full buyback.
The latter reserves inventory plus a quote-currency loss buffer without loans.
Open positions close at actual prices, including early exits and slippage;
they cannot be discarded through cancellation.

## Pair-first setup and virtual wallet

Add a manual instrument by selecting or entering base and quote symbols;
specify a type for new assets and the instrument execution steps. Bybit profiles
search public instruments and import the selected result. Required assets are
created automatically with zero balances in either mode.

The market section manages instruments, not a separate asset catalog. The
wallet manages optional asset names, explicit funding, capital floors and
ledger operations. Manual assets may also be added before choosing a pair;
Bybit asset identities come from instrument imports.
A successful instrument creation offers a link to its settlement asset, even
when empty assets are hidden. The wallet defaults to hiding never-used assets,
with an enabled Hide empty balances switch. Asset cards form an adaptive grid
and a horizontal mobile row. Balances and actions live on each card; selecting
one shows its operations below, filtered by type and UTC dates with server
sorting. Switching assets preserves filters but resets the operation page.
Profiles may store an optional venue website URL for manual or Bybit use;
this opens independently of provider API and chart links.

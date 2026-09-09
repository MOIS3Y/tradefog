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

1. **Reference Catalog**: Staff members maintain shared assets, pairs, venues,
   and instruments. Regular users read and select from existing catalog items.
2. **Profile & Wallet Setup**: The user creates a `TradingProfile` bound to one
   `Venue`, adds venue-capable assets to the profile `Wallet`, and records
   deposits.
3. **Strategy Definition**: The user defines a `TradingStrategy` with a decimal
   risk percent (e.g. `5.5%`) and a whole reward multiple (e.g. `3` for
   `1:3`), allocating fixed capital from wallet assets. The percentage defines
   the monetary `1R`; it is not the left side of the ratio, which is always
   normalized to one.
4. **Trade Preparation (Workspace)**:
   - Selects Profile, Strategy, Product, and Venue Instrument.
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

- Profiles require a name and target `Venue`.
- Wallets offer only assets active on the bound venue (`VenueWalletAsset`).
- Strategies require at least one allocated wallet asset with positive balance.

## Trade Workspace Requirements

The trade workspace provides a single unified screen for the full trade lifecycle:

1. **Context Selector**: Profile, Strategy, Product (`SPOT`, `PERPETUAL_FUTURE`,
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

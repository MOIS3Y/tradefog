# Roadmap

## Architecture Overview

Development is organized into two primary phases:

1. **Phase 1: Standalone Headless Backend API** — complete.
2. **Phase 2: Independent Frontend Application** — current phase.

## Original MVP Frontend Stages

Historical delivery sequence; the profile-owned refactor below supersedes
the shared catalog architecture of stages 3 and 4.

1. **Foundation**: Scaffold the Vue application, add the Nix development and
   production builds, serve a placeholder SPA through FastAPI, and verify the
   combined container artifact.
2. **Application Shell**: Establish design tokens, routing, localization,
   generated API types, authentication, server-state handling, and common
   loading, empty, and error states.
3. **Assets & Pairs**: Implement public catalog browsing and staff mutations
   for assets and trading pairs.
4. **Venues**: Implement venues, instruments, and venue wallet capabilities.
5. **Profiles & Capital**: Implement first-use setup, profiles, wallet
   operations, strategies, and capital allocations.
6. **Trade Workspace**: Implement drafts, checklist, ATR, position planning,
   lifecycle transitions, frozen allocation identity and timestamps, notes,
   attachments, and a ten-point quality rating.
7. **Analytics**: Implement filters and analytical visualizations, including
   per-allocation L/W and monetary performance.
8. **Release Verification**: Complete the responsive and accessibility pass,
   deployment documentation, and production verification when scheduled.

The trade workspace has an optional interactive market chart described in
[`market-chart.md`](market-chart.md); its transport migration is next.

The journal scalability refactor separates the trade list, draft creation and
individual workspace routes. Trades and catalogs use server pagination,
filtering and sorting; catalog selectors use remote search. Review completion
and quality rating are independently visible and filterable in the journal.

Each stage ends with a production frontend build, static checks, and a small
set of tests for its critical user flow before the next stage begins.

Stages 1 through 6 are complete. Stage 7 is in visual verification. Stage 8
remains deferred until release preparation is scheduled.

## Profile-owned architecture refactor

Backend: implemented profile-local assets/instruments, Bybit/manual integration
types, typed preparation, denomination-aware reservations and public Bybit API.
A new baseline migration replaces WIP schemas; old development data is not
migrated. See [backend refactor](backend-refactor.md).

Frontend: profile-local setup, nested API bindings, typed preparation and
buyback reserves are implemented. Market data uses the backend; terminal
layout, book depth bars and side modes preserve the independent manual flow.
Old global catalog routes and clients have been removed. Private execution,
market caching and server-side drawing persistence remain future increments.

## Unified profile-asset refactor

- Backend: merge account denominations and profile assets; remove wallet
  containers, retain settlement identity and all reservation invariants.
- Frontend: pair-first manual setup, searchable Bybit imports, wallet-owned
  metadata and explicit funding, optional visibility of empty assets.
- Replace the WIP baseline and DBML together. No portfolio aggregation,
  private trading, new settlement formulas or market cache in this stage.

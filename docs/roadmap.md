# Roadmap

## Architecture Overview

Development is organized into two primary phases:

1. **Phase 1: Standalone Headless Backend API** — complete.
2. **Phase 2: Independent Frontend Application** — current phase.

## Frontend Implementation Stages

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

After the MVP, the trade workspace may gain the deferred interactive market
chart described in [`market-chart.md`](market-chart.md).

Each stage ends with a production frontend build, static checks, and a small
set of tests for its critical user flow before the next stage begins.

Stages 1 through 6 are complete. Stage 7 is in visual verification. Stage 8
remains deferred until release preparation is scheduled.

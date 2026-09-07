# Roadmap

## Architecture Overview

Development is organized into two primary phases:

1. **Phase 1: Standalone Headless Backend API** (FastAPI, SQLAlchemy Async,
   Alembic, Pydantic, Loguru, Typer).
2. **Phase 2: Independent Frontend Application** (Vue.js SPA, Tabler UI,
   ApexCharts).

---

## Phase 1: Standalone Backend API

### Stage 1: Core Foundation & Domain
- [x] Extracted pure domain calculations (position sizing, 1R risk, checklist
      scoring, analytics).
- [x] Structured logging setup via Loguru.
- [x] Typed application settings with TOML and `.env` support.
- [x] Typer CLI entry points (`serve`, `config`, `version`).
- [x] Base FastAPI application setup and healthcheck endpoints.

### Stage 2: Database Persistence & Migrations
- [ ] Async SQLAlchemy engine and session management.
- [ ] Relational ORM models matching `docs/database.dbml`.
- [ ] Alembic migration environment and initial schema migrations.
- [ ] Centralized owner-scoping query utilities for user isolation.

### Stage 3: Authentication & Shared Reference Catalog API
- [ ] JWT authentication (token generation, refresh, password hashing).
- [ ] Role-based access control (Staff vs. Regular users).
- [ ] Shared catalog endpoints: Assets, Trading Pairs, Venues, Venue
      Instruments, Venue Wallet Assets.
- [ ] Staff-only catalog mutations with read-only regular user access.

### Stage 4: User Journal & Capital Management API
- [ ] Profile CRUD (active/archived states, single venue binding).
- [ ] Virtual Wallet and WalletAsset endpoints.
- [ ] Ledger operations: Deposits and Withdrawals.
- [ ] TradingStrategy and StrategyCapital fixed allocation management.

### Stage 5: Trade Lifecycle & On-Demand Market Data
- [ ] Trade workspace endpoints (Drafts, lifecycle state transitions).
- [ ] Atomic `TradeSnapshot` creation on submission.
- [ ] Capital reservation validation and locking.
- [ ] 4-question directional checklist scoring and persistence.
- [ ] On-demand daily candle fetching and `ATR(14)` calculation (Bybit,
      Binance, Yahoo Finance, Manual fallback).

### Stage 6: Analytics & Attachments
- [ ] Comprehensive analytics endpoint (R-multiples, Trajectory coordinates,
      Expectancy, Streaks, cohort filtering).
- [ ] Markdown trade notes and private file attachments upload/serving.

---

## Phase 2: Standalone Frontend (Vue.js)

### Stage 7: Frontend Application Architecture
- [ ] Vue 3 + Vite setup with TypeScript.
- [ ] Pinia state stores (Auth, Catalog, Active Profile).
- [ ] Vue Router with navigation guards and language routes (`/en/`, `/ru/`).
- [ ] Tabler UI styling integration and Dark/Light theme switching.

### Stage 8: Catalog & Profile Management Views
- [ ] Shared Catalog browser and staff management modals.
- [ ] Profile setup flow, Wallet dashboard, deposit/withdrawal modals.
- [ ] Strategy builder and capital allocation interface.

### Stage 9: Interactive Trade Workspace
- [ ] Unified trade editor (Product/Pair selector, dynamic position calculator).
- [ ] Interactive directional checklist gauge.
- [ ] Candlestick preview and ATR comparison charts (ApexCharts).
- [ ] Markdown notes editor and attachment gallery.

### Stage 10: Analytics & Hardening
- [ ] Global analytical filter bar and performance summaries.
- [ ] Interactive X/Y quality trajectory and break-even visualization.
- [ ] Client-side translations (English & Russian).
- [ ] Toast notification system and responsive design verification.

---

## Future Capabilities

- Automated order placement on selected exchanges (one-shot, non-tracking).
- Multi-currency portfolio aggregation.
- Custom strategy-specific setup checklists.

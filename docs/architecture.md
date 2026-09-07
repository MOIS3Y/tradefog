# Architecture

## System Overview

Tradefog follows a decoupled client-server architecture:

1. **Backend**: Standalone, headless REST API built with FastAPI. It handles
   authentication, data persistence, business invariants, financial
   calculations, and on-demand market data.
2. **Frontend**: Independent Single-Page Application (Vue.js) consuming the
   REST API.

The backend is fully self-sufficient and agnostic of the client.

## Technology Stack

- **Runtime & Language**: Python 3.13+
- **API Framework**: FastAPI, Uvicorn (ASGI)
- **Configuration & Validation**: Pydantic, Pydantic Settings
- **Persistence**: SQLAlchemy (async), Alembic migrations, SQLite (portable
  to PostgreSQL)
- **Logging**: Loguru (console/stdout structured logging)
- **CLI**: Typer
- **HTTP Client**: HTTPX (on-demand market data)
- **Dependency Management & Packaging**: `uv`, Nix flakes (`uv2nix`)
- **Frontend (Target)**: Vue.js, Tabler UI

## Application Structure

```text
src/tradefog/
├── api/            # FastAPI routers, endpoints, dependencies, schemas
│   └── v1/
├── config/         # Typed settings (pydantic-settings, TOML/env support)
├── db/             # SQLAlchemy engine, session maker, models, migrations
├── domain/         # Pure domain rules, enums, calculations, analytics
├── market/         # On-demand market data providers (Bybit, Binance, YFinance)
├── cli.py          # Typer CLI application entry point
├── logging.py      # Loguru configuration setup
└── main.py         # FastAPI application factory
```

### Layered Architecture

```text
HTTP Request (REST API)
    │
    ▼
API Endpoints & Schemas (FastAPI / Pydantic)
    │
    ▼
Domain & Application Services
    │
    ▼
Domain Calculations & Persistence (SQLAlchemy Async)
```

- **API Layer**: Validates transport payloads, handles route authorization,
  and serializes responses.
- **Domain Layer**: Implements business invariants, trade lifecycles, and
  financial calculations using exact decimal arithmetic. Contains no transport
  or ORM dependencies.
- **Persistence Layer**: Async database sessions, relational mapping, and
  migration history.

## Ownership & Access Control

The system defines two clear ownership zones:

1. **Shared Reference Catalog**: Staff-managed records (`Asset`, `TradingPair`,
   `Venue`, `VenueInstrument`, `VenueWalletAsset`). Regular users have
   read-only access.
2. **User Journal**: Owner-scoped records (`TradingProfile`, `Wallet`,
   `WalletAsset`, `WalletOperation`, `TradingStrategy`, `StrategyCapital`,
   `Trade`, `TradeSnapshot`, `Attachment`). All user queries are strictly
   filtered through `TradingProfile.owner`.

### Authentication & Authorization

- Authentication via JWT bearer tokens (access/refresh tokens).
- Role-based permissions: Staff vs. Regular user.
- Multi-user isolation enforced at the database repository/service boundary.

## Persistence & Invariants

- **Primary Database**: SQLite for single-node deployments; schema and ORM
  models maintain portability to PostgreSQL.
- **Financial Precision**: All monetary, price, quantity, and risk figures
  persist and compute using fixed-point decimal arithmetic.
- **Market Data**: Candles are fetched on demand and never persisted.
  Decision-time ATR snapshots are stored immutably on submitted trades.
- **Transactions**: Multi-record mutations (such as trade status transitions
  and wallet reservations) execute within atomic database transactions.

## Market Data Integrations

Market data serves as an on-demand, read-only auxiliary context:

- Sources: Bybit, Binance, Yahoo Finance, or Manual fallback.
- True Range and `ATR(14)` are computed locally from fetched daily OHLC
  candles.
- External provider outages never block manual trade journaling.

## Localization Strategy

- **API Layer**: Standardized machine-readable error codes and invariant
  data representations.
- **Frontend Layer**: Client-side internationalization (vue-i18n) supporting
  English (default) and Russian.

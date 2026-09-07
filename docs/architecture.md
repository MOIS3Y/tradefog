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

### Authentication and Catalog API

Version-one endpoints are rooted at `/api/v1`. Anyone can read the shared
catalog; a valid bearer access token with `is_staff=true` is required to create
or update an asset, pair, venue, venue instrument, or venue wallet asset.
Catalog identities are never deleted. Deactivation preserves historical
references and keeps a record out of default active-venue/instrument/capability
lists.

Catalog PATCH requests reject explicit nulls for required fields. Referenced
asset identities and pairs used by instruments cannot be reassigned; a traded
instrument's product, execution symbol and settlement asset are also locked.
Create a new catalog identity for a different market and deactivate the old
instrument. Descriptions, execution increments and availability remain editable.
Argon2 work runs in a worker thread, and JWT verification requires subject,
purpose, issue time, expiration and token identifier claims.

`POST /auth/register` creates only regular accounts. It accepts a username and
a password of at least 12 characters; passwords are stored as Argon2 hashes.
`POST /auth/token` accepts OAuth2 form credentials and issues 15-minute access
and 7-day refresh JWTs. `POST /auth/refresh` exchanges a refresh token for a
fresh pair, and `GET /auth/me` validates an access token. A disabled account
cannot authenticate or use a token issued before its deactivation. Refresh
tokens have no server-side revocation list in this stage, so the old refresh
token remains valid until it expires. Staff accounts must be provisioned
directly in the database until the administrative CLI arrives in stage four.

Set `TRADEFOG_AUTHENTICATION__JWT_SECRET_KEY` to a private value of at least
32 characters before production. The bundled default exists only for local
development and must never be used on an exposed service.

## Persistence & Invariants

- **Primary Database**: SQLite for single-node deployments; schema and ORM
  models maintain portability to PostgreSQL.
- **Financial Precision**: All monetary, price, quantity, and risk figures
  persist and compute using fixed-point decimal arithmetic.
- **Market Data**: Candles are fetched on demand and never persisted.
  Decision-time ATR snapshots are stored immutably on submitted trades.
- **Transactions**: Multi-record mutations (such as trade status transitions
  and wallet reservations) execute within atomic database transactions.

### Database Setup

From the repository root, install dependencies and apply migrations before
starting the API:

```sh
uv sync --group dev
uv run alembic upgrade head
uv run tradefog serve
```

Alembic uses the same TOML and `TRADEFOG_` environment settings as the API.
For an isolated SQLite database, set `TRADEFOG_DATABASE__SQLITE__PATH`.
The application creates the database parent directory, but never creates
tables or applies migrations automatically. `uv run alembic check` detects
model/schema drift. Migration files are packaged under `tradefog/db/migrations`.

`Database.session()` provides a transaction that commits on success and
rolls back on failure. The API's `SessionDependency` completes that transaction
before sending the response. Services flush within this boundary rather than
committing individual records. ORM relationships require explicit eager
loading to avoid implicit async database IO.

Journal reads use `owned_select(Model, authenticated_user.id)` before adding
record IDs, filters or pagination. This helper supports all eight journal
models in the current schema and rejects other models. Staff status does not
bypass journal isolation. Future mutation services must also validate that
referenced strategies, wallet assets and instruments belong to the same
profile/venue; foreign keys alone do not enforce those cross-record rules.

`ExactDecimal` implements DBML decimal precision and scale: PostgreSQL uses
`NUMERIC`, while SQLite uses canonical decimal text to avoid binary float
conversion. Inputs must be finite `Decimal` values within the declared
precision and scale. On SQLite, monetary arithmetic, numeric sorting and
aggregation must use Python `Decimal`, not SQL arithmetic, `SUM` or text
ordering. Symbols are stored trimmed and uppercase; a database check plus
the unique symbol index prevents casing variants of the same asset.

Timestamps follow the DBML's timezone-naive `timestamp` type and are treated
as UTC. Application services must normalize supplied timestamps to UTC.

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

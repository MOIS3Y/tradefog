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
- **Frontend**: Vue SPA with TypeScript, Vite, Vue Router, TanStack Query,
  Pinia, Tailwind CSS, Reka UI, Apache ECharts, and Vue I18n

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

frontend/
├── src/             # Vue application code
├── public/          # Unprocessed public assets
├── tests/           # Frontend-focused tests
├── package.json
└── package-lock.json
```

### Frontend Development and Delivery

The frontend is an independent project under `frontend/`, including its
`package.json`, lockfile, and tool-specific configuration. Repository-wide
files, including the single `.gitignore`, remain at the root. The client uses
the relative API prefix `/api/v1`; the Vite development server proxies `/api`
to the local FastAPI process. Nix provides separate backend, frontend, and
combined development commands.

The frontend and backend are built as separate Nix derivations. The production
container includes both artifacts, and FastAPI serves the compiled SPA. A
reverse proxy and TLS termination remain deployment concerns outside the
container.

The optional `[frontend] path` setting identifies the directory containing
`index.html` and compiled assets. When it is unset or invalid, the headless API
remains available and frontend requests return a safe not-found response.
Missing assets never expose filesystem paths or fall through to API routes.

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

Accounts are provisioned by the installation owner through `tradefog users`.
`POST /auth/token` accepts OAuth2 form credentials and issues 15-minute access
and 7-day refresh JWTs. `POST /auth/refresh` exchanges a refresh token for a
fresh pair, and `GET /auth/me` validates an access token. A disabled account
cannot authenticate or use a token issued before its deactivation. Refresh
tokens have no server-side revocation list in this stage, so the old refresh
token remains valid until it expires. Staff accounts can be provisioned with
`tradefog users create --staff`.

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
record IDs, filters or pagination. This helper supports all nine journal
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

### Journal and Trade Lifecycle API

Authenticated journal endpoints are rooted at `/api/v1/profiles` and
`/api/v1/trades`. Every lookup scopes through `TradingProfile.owner`; a missing
record and another user's record both return the same not-found response.
Creating a profile also creates its one-to-one wallet. Wallet balances are
derived from signed deposit and withdrawal facts plus closed-trade net P&L.
Pending and open snapshots derive wallet reservations; balances and
reservations are not duplicated in mutable columns.

Wallet assets must reference an active capability on the profile venue.
Withdrawals preserve both active trade reservations and capital committed to
active strategies. Strategy capital is allocated per wallet asset and cannot
exceed the asset balance across active allocations. Its amount, plus strategy
risk and reward rules, becomes locked by the first submitted trade.
Deposit-floor and strategy statuses are advisory and never reject a
discretionary trade.

Trade identity and checklist fields remain editable in `draft`; Markdown notes
and analytical trade date remain correctable later. Submission to
`pending_entry` or `open` locks the trade, validates its settlement allocation,
calculates an executable position, checks risk capacity and wallet notional,
then creates exactly one immutable `TradeSnapshot` in the same transaction.
Reservations release when a trade is cancelled or closed. Closing records
signed net P&L, and review completion is tracked independently.

`POST /trades/{trade_id}/plan` previews the same validated calculation without
creating a snapshot or reservation. When ATR context exists, the preview also
reports whether the take-profit move fits within the advisory 75% ATR limit.
`PUT /trades/{trade_id}/plan` persists the entry and stop in the draft context;
submission accepts only a lifecycle status and freezes that saved plan.

Saved plan inputs, checklist answers, and the latest draft ATR are stored
inside `draft_context`. Automatic ATR fetches run outside the event loop through
the venue's configured Bybit, Binance, or Yahoo provider. Manual ATR remains
available when a provider is absent or unavailable. Candles are returned for
immediate preview and are never persisted; only decision-time ATR fields enter
the immutable snapshot.

### Analytics, Attachments and Administration

`GET /api/v1/analytics` calculates owner-scoped results exclusively from
closed trades and immutable planned risk. It supports named and custom date
periods plus profile, strategy, product, instrument, pair, and settlement-asset
filters. Results include R-multiples, expectancy, profit factor, drawdown,
streaks, cumulative trajectory, and decision-discipline X/Y coordinates.
SQLite financial values are loaded and calculated in Python with `Decimal`.

Trade attachments are verified JPEG, PNG, GIF, or WebP images stored beneath
the configured private media root. Only generated storage keys reach the
filesystem; API responses never expose them. Metadata and content endpoints
are owner-scoped, content responses disable shared caching and MIME sniffing,
and there is no public static-files mount. Apply migration `0002` before using
attachment endpoints.

Administrative user management is available through `tradefog users` commands
for account creation, listing, activation, staff-role changes, and password
replacement.

## Market Data Integrations

Market data serves as an on-demand, read-only auxiliary context:

- Sources: Bybit, Binance, Yahoo Finance, or Manual fallback.
- True Range and `ATR(14)` are computed locally from fetched daily OHLC
  candles.
- External provider outages never block manual trade journaling.

## Localization Strategy

- **API Layer**: Standardized machine-readable error codes and invariant
  data representations.
- **Frontend Layer**: Client-side internationalization supporting
  English (default) and Russian.

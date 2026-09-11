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
├── market/         # Provider-neutral async public data, Bybit adapter and ATR
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

Frontend tooling uses Node.js 22.22.2 or newer in the Node 22 line (jsdom's
minimum), Vite 8 and Vitest 5. Dependencies are locked with npm. TypeScript
stays on 5.9 until `openapi-typescript` supports newer compiler majors; do not
bypass its peer requirement with forced installs. Update `npmDepsHash` in
`flake.nix` whenever the frontend lockfile changes.

The frontend and backend are built as separate Nix derivations. The production
container includes both artifacts, and FastAPI serves the compiled SPA. A
reverse proxy and TLS termination remain deployment concerns outside the
container.

Market data is an official headless API feature under /api/v1/venues, with a
provider-neutral service and async Bybit transport. Chart rendering remains an
optional frontend module. The SPA uses authenticated Tradefog market endpoints,
not browser-to-exchange requests. Profile-local setup supports selected Bybit
imports and manual specifications without a shared staff catalog. See [backend refactor](backend-refactor.md).

The market UI polls candles and visible depth independently, one second after
each stream completes. Requests within a stream never overlap; timeframe
changes cancel only candles. Hidden work is aborted, transient failures back
off per stream, and provider cooldowns apply to both. Late responses cannot
update a different chart context. REST contracts and exact backend decimals
remain unchanged.

Chart periods reuse one canvas instance. A feature-local, in-memory history
cache is keyed by provider/product/symbol/timeframe, with a ten-minute idle
TTL, eight ranges and 20,000 candles total. LRU eviction removes whole ranges;
oversized ranges are not cached. Returning to a period displays history first,
then refreshes the last two candles and reconciles gaps before live updates.
Cached data is not considered a fresh price. Logout clears the cache and
invalidates in-flight cache writes; reload also discards it. No persistent
browser storage or server cache is involved. Snapshot-only book rendering
and unchanged-candle suppression keep polling out of unrelated UI updates.
The market feed also publishes live closing prices to the depth panel without
an additional request; cached history alone does not update that price.
Order book grouping consumes all 50 received levels before limiting visible
rows to 20. Display increments derive from observed price precision, not an
inferred exchange tick specification. Indicator toggles operate on the existing
canvas and loaded OHLCV data. Market UI copy lives under `marketChart` in the
shared journal translations; the feature uses the global i18n instance.

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

All journal and market identities belong to TradingProfile.owner_id.
TradingAsset and TradingInstrument are profile-local; no staff-maintained
catalog exists. Authenticated users manage their own profiles, metadata,
virtual wallets and strategies. Staff remains an account-administration role.

### Authentication and Profile API

All business and market endpoints require JWT authentication. Public market
means no exchange key, not anonymous application access. Profile collections
use /profiles/{id}/assets, /instruments, /wallet, /strategies and nested
allocations; /trades remains a cross-profile owner-scoped list.
Profile, asset, instrument, strategy, allocation and wallet-asset lists use
server pagination, search where meaningful and allowlisted stable sorting.
Wallet operations are paged newest-first and never edited except for notes.

Mutations serialize financial checks: SQLite uses BEGIN IMMEDIATE before
reads; PostgreSQL locks the authenticated user row before modifying profiles.
This conservatively serializes all mutations for one user, including different
profiles. It is deliberately broader than a per-profile lock. Network timeout
bounds also limit long-running import/ATR requests; no distributed lock exists.

A fresh 0001 baseline replaces the WIP migration history. Existing development
databases require an explicit reset, not an automatic data migration. Optional
user contact fields are exposed by GET/PATCH /auth/me; email is nonunique and
not used for authentication or recovery.

Accounts are provisioned by the installation owner through `tradefog users`.
`POST /auth/token` accepts OAuth2 form credentials and issues 15-minute access
and 7-day refresh JWTs. `POST /auth/refresh` exchanges a refresh token for a
fresh pair, and `GET /auth/me` validates an access token. A disabled account
cannot authenticate or use a token issued before its deactivation. Password
changes through `POST /auth/password` or the CLI increment an account credential
version, invalidating all previous access and refresh tokens. Legacy JWTs
without a version are accepted only while the account version is zero.
Refresh tokens otherwise remain valid until expiry. Staff can be provisioned with
`tradefog users create --staff`.

The settings page exposes contact metadata, account language and password
changes with current-password verification. Optional `preferred_locale` on
`GET/PATCH /auth/me` accepts `en`, `ru` or null; null preserves the browser's
language until the user saves a preference. Passwords use the shared 12–128
character policy. Successful changes end the current browser session too.
Apply Alembic migrations before starting the updated application.

Swagger UI at `/docs` already supports authentication: choose **Authorize**,
enter the account username and password, leave client ID/secret empty, and
authorize. Try `GET /api/v1/auth/me` to verify access. Swagger uses the same
OAuth2 password endpoint as the SPA; reauthorize after token expiry or a
password change. SMTP, email verification/recovery and exchange API-key
storage are not part of account settings yet.

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
A profile owns virtual account assets directly. Wallet balances are
derived from signed deposit and withdrawal facts plus closed-trade net P&L.
The profile directory uses server-side pagination, archive filtering and
literal search across profile and venue names, with stable name/ID ordering.
Ledger fact amounts, kinds, and timestamps cannot be patched; the dedicated
operation-note endpoint changes only optional explanatory text.
Immutable TradeReservation rows attached to pending/open snapshots derive
wallet reservations; balances and active flags are not duplicated.

Operations and allocations reference an unarchived profile asset directly.
Withdrawals preserve both active trade reservations and capital committed to
active strategies. Strategy capital is allocated per wallet asset and cannot
exceed the asset balance across active allocations. Its amount, plus strategy
risk and reward rules, becomes locked by the first submitted trade.
Deposit-floor and strategy statuses are advisory and never reject a
discretionary trade.

Trade identity and checklist fields remain editable in `draft`; Markdown notes
remain correctable later; analytical trade date locks on submission. Submission to
`pending_entry` or `open` locks the trade, validates its settlement allocation,
calculates an executable position, checks risk capacity and all denomination-specific reserves,
then creates exactly one immutable `TradeSnapshot` in the same transaction.
Reservations release when a trade is cancelled or closed. Closing records
signed net P&L, and review completion is tracked independently.

`GET /trades/{trade_id}/planning-context` supplies exact instrument, strategy, and
capital inputs for the frontend's synchronous Decimal calculation. The user
edits only entry and stop; take profit and quantity remain derived. `POST
/trades/{trade_id}/plan/preview` provides the same preview to headless API clients.
`PUT /trades/{trade_id}/plan` revalidates and persists entry and stop while
still allowing an underfunded draft. Submission rechecks current capital and
freezes the saved plan.

Saved entry/stop, four checklist answers and ATR facts live in the typed
TradePreparation table. Incomplete price anchors are allowed until submission.
Bybit automatic ATR uses the same async provider as chart candles, without
internal HTTP calls; manual ATR remains available for both integration types.
Changing the instrument or trade date clears stale preparation ATR.

Spot/cash short reserves owned base inventory and a quote loss buffer. Other
supported plans reserve virtual 1x notional. Sale proceeds are not spendable.
Open trades must close with actual price and net P&L; losses beyond reserves
are recorded even if the resulting virtual balance is negative.

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
and there is no public static-files mount. Attachments are included in the new baseline migration.

Administrative user management is available through `tradefog users` commands
for account creation, listing, activation, staff-role changes, and password
replacement.

## Market Data Integrations

Market data serves as an on-demand, read-only auxiliary context:

- Source: public Bybit; manual profiles never require network access.
- True Range and `ATR(14)` are computed locally from fetched daily OHLC
  candles.
- External provider outages never block manual trade journaling.

## Localization Strategy

- **API Layer**: Standardized machine-readable error codes and invariant
  data representations.
- **Frontend Layer**: Client-side internationalization supporting
  English (default) and Russian.

## Unified profile assets

The profile owns account denominations directly. There are no Wallet or
WalletAsset tables. WalletOperation, StrategyCapital and TradeReservation
reference TradingAsset through asset_id; financial calculations remain Decimal
and independent of the presentation layer.

GET/POST /api/v1/profiles/{profile_id}/assets and GET/PATCH/DELETE of one asset
combine identity management with derived balance/reservation values.
GET/POST /api/v1/profiles/{profile_id}/assets/{asset_id}/operations and PATCH
of one operation preserve immutable financial facts with note-only correction.
The asset list supports hide_empty before server pagination.

Instrument creation is discriminated by mode (manual or bybit), matching the
immutable profile venue. Manual requests carry base/quote symbols and execution
rules; Bybit requests carry a selected executable symbol and product.
The public instrument list accepts q and provider cursor; search skips empty
provider pages and exposes the next cursor without persisting the catalog.

Baseline 0001 is replaced for WIP; old development databases are incompatible.
Recreate only a confirmed disposable development database with the application
stopped, then run alembic upgrade head inside nix develop. No data migration,
compatibility endpoints or automatic runtime database deletion are provided.

### Profile browsing

- `GET /api/v1/profiles/{profile_id}/operations` returns a paginated ledger
  across profile assets, including archived ones. Filters: `asset_id`,
  `kind`, inclusive UTC `date_from/date_to`; sort: `created_at`,
  `order=asc|desc` (default descending). Each row includes `asset_symbol`.
  Create and note-patch requests stay nested under the asset.
- Instrument collections accept `product` and server sorting by
  `symbol` or `product`. Counts reflect filters before pagination.
- Direct asset creation is manual-only; Bybit imports establish identities.
  Ledger browsing and market filters require no new database tables.

- Profiles expose optional nullable `venue_url` in create, patch and read
  responses. Migration 0002 adds the column without replacing the baseline.
  It is a credential-free HTTP(S) browser link, never a market transport
  configuration. The wallet UI uses the existing profile ledger endpoint
  with `asset_id`; unfiltered headless access remains supported.

# Profile-owned backend refactor

## Delivery boundary

The approved change replaces the staff catalog with profile-owned assets and
instruments. Implement the backend first, then migrate the frontend. No API or
data compatibility layer is required. The existing development database may be
reset only after resolving its actual configured path; never clear a data
directory or attachments implicitly.

`database.dbml` is now the installed schema, implemented by the static
`0001_profile_schema` baseline. The proposal and old catalog migrations have
been removed. Existing databases require an explicit reset; this is not an
in-place upgrade from the old catalog schema.

## Public market API

The application exposes authenticated public-market routes:

```text
GET /api/v1/venues
GET /api/v1/venues/{venue_type}
GET /api/v1/venues/{venue_type}/public/instruments
GET /api/v1/venues/{venue_type}/public/instruments/{symbol}
GET /api/v1/venues/{venue_type}/public/klines
GET /api/v1/venues/{venue_type}/public/orderbook
```

`public` means no exchange key, not anonymous Tradefog access. Instruments use
`product` and an optional exact `symbol` or upstream cursor. Spot metadata has
no cursor; linear metadata returns a continuation cursor. Browsing never
imports catalog rows. Candle queries use `symbol`, `product`, `timeframe`,
`limit` (1–500) and optional exclusive `before` in UTC milliseconds. Depth uses
`symbol`, `product` and `limit` (1–50 per side). Monetary values serialize as
decimal strings. Timestamps are UTC milliseconds.

The normalized provider protocol, async Bybit implementation and lifespan-owned
transport are independent of ORM, trade lifecycle and chart libraries. Eight
outbound slots, a one-second slot acquisition deadline and a twelve-second
request deadline bound network work. Provider cooldown is process-local and
shared by consumers of the new service; it is not distributed coordination.
HTTP 403 causes at least ten minutes of cooldown, 429 at least one minute;
provider throttling codes and Retry-After are respected. There are no internal
retry loops or candle persistence. Logs contain provider, outcome and duration,
not credentials or full payloads.

`PublicMarketService.atr` uses the same candle provider and existing pure ATR
formula, including historical date bounds. The trade ATR endpoint now uses
this service and returns calculated business data, not raw candles. Manual
ATR needs no provider. Legacy Binance/Yahoo providers have been removed.
The frontend now uses these authenticated application endpoints; no exchange
REST payload parsing remains in the browser.

## Implemented journal backend

- Replaced shared catalogs with TradingProfile.venue_type (bybit/manual),
  TradingAsset and TradingInstrument. Enforce same-profile references and
  owner scoping for every child. Import Bybit metadata only for selected
  instruments; manual never calls an exchange. Both keep virtual wallets.
- Added user contact fields and timestamps, with username authentication
  unchanged. Add typed TradePreparation instead of JSON, preserving nullable
  draft inputs and locking decision inputs on submission.
- Implemented TradeReservation and serialized capital mutations. SQLite
  acquires BEGIN IMMEDIATE before mutation reads; PostgreSQL locks the
  authenticated user row, serializing all their profile mutations.
  Spot/cash long and virtual 1x perpetual reserve notional. Spot/cash short
  means sale of owned inventory followed by full buyback: reserve base quantity
  and quote loss buffer. Never credit sale proceeds as spendable funds.
- Close with actual exit and net P&L, allow slippage beyond reserved risk,
  account P&L once, and prohibit cancellation of open trades. Keep historical
  reservation requirements but count only pending/open rows as active.
- Replaced catalog APIs with profile-nested asset/instrument APIs, retain
  virtual wallet/strategy/allocation operations, introduce explicit plan
  preview, and switch trade ATR to the shared market service. Remove legacy
  Binance/Yahoo providers. Add metadata refresh without overwriting archives.
- Keep monetary analytics partitioned by profile and denomination; compare
  cross-profile performance in R. Preserve attachments, notes and reviews.
- Replaced the baseline and canonical DBML. Focused SQLite tests cover fresh
  migrations, ownership, exact money, competing reservations, all supported
  funding modes, actual losses, typed preparation and mocked Bybit import/ATR.
  DBML table/column parity and PostgreSQL offline migration SQL were checked.
  Live PostgreSQL integration remains a separate verification requirement.

Profile children are rooted at `/api/v1/profiles/{profile_id}`: `/assets`,
`/instruments`, `/assets/{asset_id}/operations`, `/strategies`, and
`/strategies/{strategy_id}/allocations`. Lists are paginated with allowlisted
sorting. Trades retain `/api/v1/trades`; planning uses `GET /{id}/planning-context`,
`POST /{id}/plan/preview` and `PUT /{id}/plan`. Partial preparation is valid
in draft; submission freezes the complete snapshot and reservation rows.

## Implemented frontend stage

Generated API types and profile-local setup replace the shared catalog pages.
Bybit searches/imports specs; manual creates pairs and required assets atomically.
All funding remains explicitly virtual. Wallet operations are paginated per asset,
with denomination shown on every row. Nested mutations carry profile and
strategy identities explicitly. Market requests use the application API,
preserving lazy chart loading, drawings, fullscreen, snapshots, history,
one-second post-cycle polling, visibility pauses and server cooldowns.

The terminal layout places chart and book left, position inputs/results right,
and the unchanged risk bar across the bottom. Unsupported/manual markets use
that same position component at full width. Mobile order is chart, collapsible
book, inputs, results, risk bar. Book depth bars and side visibility modes are
implemented without price grouping. Existing design tokens, RU/EN and keyboard
access are retained. Typed partial anchors survive draft saves. Spot/cash
buyback previews distinguish owned inventory and cash risk reserves;
submission remains authoritative on the server.

## Deferred features

No private credentials, exchange execution, partial fills, real balance sync,
leverage, caches or task queues. Future caches wrap the public provider/service
boundary without changing journal accounting. Connections and exchange orders
will be separate future entities, not speculative columns on Trade.

## Pair-first simplification

TradingAsset now also owns account settings. Wallet and WalletAsset tables are
removed, and ledger operations, allocations and reservations reference asset_id.
Instrument names are derived; descriptive names belong to assets.
Settlement identity and the supported-product calculation limits are retained.
The wallet hides never-used assets by default and can reveal them without writes.
The static WIP baseline replaces the previous schema without compatibility.

Verification for unified assets: 44 backend tests and 58 frontend tests pass.
The production Vite bundle builds; its existing large-chunk warning remains.
DBML matches all 12 ORM tables and their columns. Fresh SQLite migration and
PostgreSQL offline SQL generation pass; live PostgreSQL was not exercised.
Browser checks cover the desktop wallet and mobile manual instrument form
with mocked API responses. No working development database was deleted.

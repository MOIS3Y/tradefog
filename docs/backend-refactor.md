# Profile-owned backend refactor

## Delivery boundary

The approved change replaces the staff catalog with profile-owned assets and
instruments. Implement the backend first, then migrate the frontend. No API or
data compatibility layer is required. The existing development database may be
reset only after resolving its actual configured path; never clear a data
directory or attachments implicitly.

`database-profile-owned.dbml` is the review target, not the installed schema.
Once models and a fresh baseline migration implement it, replace
`database.dbml` and remove the proposal. Do not claim the transition complete
while the old ORM or journal endpoints are still present.

## Implemented first slice

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
formula, including historical date bounds. The old trade ATR endpoint has not
yet been switched to it. The frontend still uses its existing direct adapter
until its separate stage. Existing catalog providers remain until the model
transition removes their callers.

## Remaining backend implementation

- Replace shared catalogs with TradingProfile.venue_type (bybit/manual),
  TradingAsset and TradingInstrument. Enforce same-profile references and
  owner scoping for every child. Import Bybit metadata only for selected
  instruments; manual never calls an exchange. Both keep virtual wallets.
- Add user contact fields and timestamps, with username authentication
  unchanged. Add typed TradePreparation instead of JSON, preserving nullable
  draft inputs and locking decision inputs on submission.
- Implement TradeReservation and profile-serialized capital mutations.
  Spot/cash long and virtual 1x perpetual reserve notional. Spot/cash short
  means sale of owned inventory followed by full buyback: reserve base quantity
  and quote loss buffer. Never credit sale proceeds as spendable funds.
- Close with actual exit and net P&L, allow slippage beyond reserved risk,
  account P&L once, and prohibit cancellation of open trades. Keep historical
  reservation requirements but count only pending/open rows as active.
- Replace catalog APIs with profile-nested asset/instrument APIs, retain
  virtual wallet/strategy/allocation operations, introduce explicit plan
  preview, and switch trade ATR to the shared market service. Remove legacy
  Binance/Yahoo providers. Add metadata refresh without overwriting archives.
- Keep monetary analytics partitioned by profile and denomination; compare
  cross-profile performance in R. Preserve attachments, notes and reviews.
- Replace baseline migrations, test fresh SQLite/PostgreSQL behavior and
  update architecture, domain, product, analytics and roadmap documents.

## Frontend stage

After backend acceptance, regenerate API types and replace catalog pages with
profile-local setup. Bybit selects/imports specs; manual edits specs. All
funding is manual virtual funding. Move market requests to the application
API, preserving lazy chart loading, drawings, fullscreen, snapshots, history,
one-second post-cycle polling, visibility pauses and cooldowns.

Use the agreed terminal layout: chart and book left, position inputs/results
right, risk bar across the bottom. Unsupported markets use the same position
component at full width. Mobile order is chart, collapsible book, inputs,
results, risk bar. Add book depth bars and side visibility modes, not price
grouping. Preserve the existing design tokens, RU/EN and keyboard access.

## Deferred features

No private credentials, exchange execution, partial fills, real balance sync,
leverage, caches or task queues. Future caches wrap the public provider/service
boundary without changing journal accounting. Connections and exchange orders
will be separate future entities, not speculative columns on Trade.

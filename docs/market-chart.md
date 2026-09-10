# Market Chart

## Status and Purpose

Planned frontend feature for market analysis inside the trade workspace.
The first increment supports Bybit charts and order books, reducing the need
to switch between Tradefog and the exchange. It is not a tick-accurate trading
terminal or an authoritative source for financial calculations.

The standalone API remains independent. ATR fetching, calculations, snapshots,
and trade lifecycle rules stay unchanged. No general market-data endpoint,
server candle cache, Redis, or task queue is required. Automated trading is
outside this scope.

## Module Boundary and Providers

Isolate components, normalized types, polling, provider adapters, and styles
in `features/market-chart`. Load the core `klinecharts` package lazily.
The trade page supplies instrument context; the module never changes position
inputs or participates in saving the trade.

A frontend adapter registry declares supported market types, timeframes,
chart and order-book capabilities separately, refresh policy, and exchange
instrument links. The venue's configured provider identifies the source, but
server-side ATR support does not imply frontend chart support. Initially
support Bybit spot and linear perpetual instruments. Adding a provider should
require an adapter, registration, and tests, not changes to the position form
or market components.

Public REST requests go directly from the browser to the provider, without
exchange keys, Tradefog credentials, or private trade data. Verify browser
CORS and network accessibility for each adapter. Do not silently substitute
another venue or add a backend proxy fallback. Provide an "Open in Bybit" link.

Normalize candles in ascending order with UTC millisecond timestamps and
decimal-string OHLC values; volume and turnover may be absent. Convert to
numbers only at the visualization boundary. Preserve decimal precision in
order-book prices and quantities.

## Layout and Styling

Use Tradefog's dark surfaces, semantic tokens, IBM Plex fonts, compact
controls, and restrained motion. Avoid flashing prices and a separate theme.

```text
Wide screen with market support:
[ Chart                  | Order book | Position parameters ]
[ Existing position risk bar and calculation summary        ]
[ Checklist | ATR ]
[ Journal and review ]

Without market support:
[ Long / Short                                              ]
[ SL                 | Entry              | Calculated TP    ]
[ Existing position risk bar and calculation summary        ]
[ Checklist | ATR ]
[ Journal and review ]
```

- Use one position form: vertical beside the market, horizontal when it fills
  the available width. Preserve Long/Short, SL -> Entry -> derived TP,
  validation, and lifecycle locking. Do not draw trade levels on the chart.
- Unsupported capabilities leave no empty columns or large placeholders.
  Without market support, the ordinary trade page remains complete.
- At intermediate widths move parameters below the market block. On mobile
  use chart -> collapsible order book -> parameters -> position risk bar.
  Never insert parameters between the chart and order book.
- A supported provider's network error stays inside its panel; it must not
  switch to the unsupported layout or block journal work.
- Removing the optional module restores the ordinary layout without changing
  trade logic, financial calculations, or API contracts.

## Loading and Refresh

Use REST for history, recent candles, and order-book snapshots. Keep loaded
history in page memory; no persistent quote cache, WebSocket connection, or
cross-tab coordination is needed in the first increment.

- Load history on initialization, timeframe changes, and backward scrolling.
  Offer multiple adapter-supported timeframes from the first release.
- For Bybit, request recent candles and the visible book in parallel, then
  wait five seconds after the cycle finishes before repeating. This is one
  refresh cycle, not an atomic exchange snapshot; track freshness separately.
- Show 20 bid and 20 ask levels with price, size, cumulative size, and spread.
  The book is always current, including when viewing a closed trade or an
  historical chart period. Do not imply historical liquidity or tick accuracy.
- Merge candles by opening time without recreating the chart. Preserve zoom
  and viewport during refresh and history loading.
- Do not overlap refresh cycles. Abort obsolete requests on context changes
  and disposal. Pause while the page/module is hidden; do not poll a collapsed
  book. Refresh on return and reconcile any missed candles after a pause.
- Retain last successful data on errors and mark delayed panels as stale.
  Back off transient failures from 5 to 10, 20, 40, then 60 seconds; successful
  recovery restores normal cadence. Honor provider rate-limit cooldowns
  separately. Reload resets local backoff, not an exchange-side ban.
- Keep loading and failures local to each panel, without clearing usable
  data or blocking trade editing.

## Drawing and Screenshots

Provide horizontal levels and rays, trend segments and sloped rays, deletion
of selected drawings, and clear-all. Drawings never modify the saved position.
A custom Long/Short Position drawing is deferred.

Retain a bounded, versioned set of drawings locally in the browser, scoped to
user, trade, and instrument. Store supported types, time/price anchors, and
allowed styles, not library runtime objects. Preserve drawings across
timeframe changes, reloads, and trade closure. Local storage is best-effort:
clearing browser data loses drawings; they are not synchronized across
devices or included in server backups. Separate storage access from rendering
so an API-backed implementation can be added later.

"Save snapshot to journal" exports the visible chart including drawings and
uploads the image through existing private attachments. Failed uploads allow
retry without clearing drawings. No new attachment storage is needed.

## Delivery and Verification

The first feature includes the Bybit adapter, multi-timeframe chart, REST
order book, responsive position layout, basic drawings with local retention,
and screenshot attachment. No backend migrations are needed.

Test normalization, history boundaries, incremental updates, cancellation,
hidden-page polling, backoff, drawing restoration, and screenshot upload.
Verify browser CORS, desktop/mobile layouts, unsupported providers, and
unchanged trade operations when the module is absent or fails.

Owner-scoped server storage of editable annotations is a separate later
feature, not server market-data ingestion. WebSocket updates and additional
provider adapters are independent future increments.

## References

- [KLineChart data integration](https://klinecharts.com/en-US/guide/data-integration)
- [KLineChart overlays](https://klinecharts.com/en-US/guide/overlay)
- [Bybit candles](https://bybit-exchange.github.io/docs/v5/market/kline)
- [Bybit order book](https://bybit-exchange.github.io/docs/v5/market/orderbook)
- [Bybit rate limits](https://bybit-exchange.github.io/docs/v5/rate-limit)

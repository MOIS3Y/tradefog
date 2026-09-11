# Market Chart

## Status and Purpose

Implemented optional frontend feature for market analysis in the trade
workspace.
The first increment supports Bybit charts and order books, reducing the need
to switch between Tradefog and the exchange. It is not a tick-accurate trading
terminal or an authoritative source for financial calculations.

The backend now exposes normalized authenticated market data through
`/api/v1/venues/{venue_type}/public/{instruments,klines,orderbook}`. Trade ATR
uses the same provider service but returns its own calculated business result.
Neither API nor manual journal functionality depends on the chart module.
There is no candle persistence, cache, Redis or task queue. Automated trading
is outside this scope. See `backend-refactor.md` for the API contract.

Migration status: both stages are implemented. The frontend consumes the
Tradefog API and profile-owned instrument context. Exchange payload handling,
provider limits and ATR fetching stay in the backend.

## Module Boundary and Providers

Components, normalized types, polling, and provider adapters live in
`features/market-chart`. The core `klinecharts` package loads lazily.
Market panel styles live in `styles/_market-chart.scss`; trade workspace
layout lives in `styles/_trades.scss`. Both use the common stylesheet entry
point and the `.tf-app` namespace.
The trade page supplies instrument context; the module never changes position
inputs or participates in saving the trade.

`trades/TradeMarketWorkspace.vue` is the removable integration bridge. It
resolves venue context and supplies the existing attachment-upload callback;
its default slot contains the unchanged position form. Replacing that bridge
with its slot content restores the ordinary workspace.

A frontend capability registry declares supported market types, timeframes,
chart and order-book capabilities separately, refresh policy, and exchange
instrument links. The profile's venue type identifies the source, but
server-side ATR support does not imply frontend chart support. Initially
support Bybit spot and linear perpetual instruments. Adding a provider should
require an adapter, registration, and tests, not changes to the position form
or market components.

The transport uses authenticated Tradefog REST requests; only the
backend talks to the exchange. Public means no exchange key, not anonymous
application access. Do not silently substitute another venue. Preserve an
"Open in Bybit" link, visibility pauses and error cooldowns. Provider
normalization belongs to the backend; chart rendering and refresh scheduling
belong to this optional frontend module.

Normalize candles in ascending order with UTC millisecond timestamps and
decimal-string OHLC values; volume and turnover may be absent. Convert to
numbers only at the visualization boundary. Preserve decimal precision in
order-book prices and quantities.

## Layout and Styling

Use Tradefog's dark surfaces, semantic tokens, IBM Plex fonts, compact
controls, and restrained motion. Avoid flashing prices and a separate theme.
Chart numbers group thousands with a non-breaking space, not a comma;
Display precision comes from significant decimal places in received OHLC
and volume values, ignoring trailing zeros. It can grow when loading older
history or new candles, but never shrinks during a chart's lifetime. Catalog
price/quantity steps apply only to order planning; no instrument-metadata
request is needed for the chart.

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
- The chart toolbar switches between candles, OHLC bars, and a line with
  area fill without fetching data again. Full screen includes only the chart
  and its controls, preserving the canvas and drawings. Escape or the same
  button exits; unsupported browser requests show a local explanation.
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
  wait one second after the cycle finishes before repeating. This is one
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
  Back off transient failures to 10, 20, 40, then 60 seconds; successful
  recovery restores normal cadence. Honor provider rate-limit cooldowns
  separately. Reload resets local backoff, not an exchange-side ban.
- Keep loading and failures local to each panel, without clearing usable
  data or blocking trade editing.

## Drawing and Screenshots

Provide all 15 built-in step-based overlays, grouped as lines, channels,
Fibonacci, and labels. The left drawing rail remembers each group's last
choice during the session. At widths up to 620 px, a Drawing button reveals
the controls. Brush and a custom Long/Short Position drawing are deferred.
Drawings never modify the saved position.

Choose a palette or custom HEX color for the selected drawing and subsequent
drawings. Lines, text and pointers share the foreground color; label
backgrounds retain contrast. Text annotations and level labels ask for up to
200 single-line characters after placement and support later editing.
Cancelling new text removes only that new annotation. Escape or changing
tools cancels unfinished geometry. Completed drawings remain editable and
can be deleted individually or cleared with confirmation.
Delete removes the selected drawing when focus is on the chart or page;
text inputs, dialogs and controls outside the chart retain their own keys.
The chart enables pointer events on the built-in text figures so labels can
be selected, moved, recolored and edited after restoration.

Retain a bounded, versioned set of drawings locally in the browser, scoped to
user, trade, and instrument. Version 2 stores supported types, one to three
time/price anchors, HEX color and optional text, not library runtime objects.
Read version 1 under the same key using the original blue drawing color;
upgrade on the next save. Bound each document to 100 drawings and 128 KiB.
Save completed changes only; storage failures leave the visible chart usable.
Menus and text dialogs stay inside the fullscreen chart subtree. Preserve
drawings across
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
and screenshot attachment. Drawing persistence remains browser-local.

Focused frontend tests cover adapters, refresh lifecycle, local storage,
incremental canvas updates, snapshot retries, and unsupported-provider fallback.
Chrome verification of the refactor uses mocked normalized API responses for
wide/mobile layouts (1600 and 390 px). Focused tests cover authenticated market
transport, server cooldowns, side visibility, drawing retention and manual
fallback. This does not replace a live provider availability check.

Test normalization, history boundaries, incremental updates, cancellation,
hidden-page polling, backoff, drawing restoration, and screenshot upload.
Verify desktop/mobile layouts, unsupported providers, and
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

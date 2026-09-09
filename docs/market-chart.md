# Market Chart

## Status

Deferred until the MVP is complete. This document records the intended
direction and does not expand the current release scope.

## Purpose

The trade workspace may include an interactive candlestick chart powered by
the core `klinecharts` package. The chart supports planning and review; it is
not an execution terminal and never becomes authoritative for financial
calculations or trade state.

The chart should:

- show historical candles for the selected venue instrument;
- support provider-compatible timeframes;
- display Entry, Stop Loss, Take Profit, actual Exit, and later current price;
- allow temporary drawing and annotations;
- export the visible chart and attach it to the trade as a screenshot;
- remain visually consistent with the Tradefog dark interface.

## Architecture

The frontend must not call Binance, Bybit, Yahoo Finance, or another market
provider directly. KLineChart receives normalized data from a dedicated
Tradefog market-data API, which delegates to the existing provider layer.

```text
KLineChart
    |
    v
Tradefog candles API
    |
    v
Market-data service
    |
    +-- Binance
    +-- Bybit
    +-- Yahoo Finance
```

The existing trade ATR endpoint remains focused on ATR decision context. It
must not become the general chart data source, although both features may
reuse the same provider adapters and candle types internally.

## Market-Data Contract

Add an authenticated, read-only endpoint for candles of a concrete
`VenueInstrument`. It should accept a timeframe, a time boundary, and a
bounded limit so KLineChart can initialize and request older or newer data.

The response should contain chronologically ordered candles with:

- millisecond timestamp;
- open, high, low, and close as decimal strings;
- optional volume and turnover as decimal strings;
- source and observation metadata where useful.

The backend validates ownership-safe access, resolves the configured venue
provider and execution symbol, and normalizes provider-specific intervals.
Unsupported periods and unavailable providers return explicit domain errors.
Provider timeouts or failures affect only the chart and never prevent work on
the rest of the trade.

Use a short-lived backend cache and coalesce identical concurrent requests.
This protects external providers from repeated chart initialization, scrolling,
and multiple browser tabs even in a small self-hosted installation.

## Frontend Behavior

- Load KLineChart lazily with the trade chart component so it does not enlarge
  the initial application bundle.
- Convert decimal strings to chart numbers only at the visualization boundary.
  Tradefog calculations and persisted values remain exact decimals.
- Expose only periods supported by the selected provider and instrument.
- Show a quiet unavailable state when a venue has no market-data provider.
- Keep loading and provider errors local to the chart module.
- Stop background activity when the chart is hidden or the browser tab is not
  visible.

Entry, Stop Loss, and Take Profit overlays come from the editable draft or the
immutable trade snapshot. Exit appears after closure. These system overlays
are visually distinct from user drawings and cannot be moved after the trade
leaves the draft state.

## Live Updates

The first implementation is historical and daily only. A later increment may
update the current candle through infrequent polling, initially every 15 to 30
seconds. Polling is opt-in, limited to open trades, paused for hidden tabs, and
stopped when the component is destroyed.

WebSocket subscriptions may replace polling later without changing the chart
component contract. Provider-specific streaming details remain behind the
backend market-data boundary.

## Drawings and Screenshots

User overlays are initially ephemeral. The user may draw on the chart, export
the visible chart including overlays, convert the result to a `Blob` or `File`,
and upload it through the existing private trade attachment endpoint.

Persisting editable drawings is a separate future capability. If required,
overlay definitions should be serialized as owner-scoped trade data rather
than embedded in notes or treated as authoritative trade parameters.

## Delivery Increments

1. Add the general candles API and a lazy-loaded daily read-only chart with
   unavailable, loading, and error states and locked trade-level overlays.
2. Add supported timeframe selection and optional polling of the current
   candle.
3. Add drawing tools and one-action screenshot attachment.
4. Consider persisted editable overlays and WebSocket updates only after the
   preceding workflow proves useful.

## References

- [Data integration](https://klinecharts.com/en-US/guide/data-integration)
- [KLineChart overlays](https://klinecharts.com/en-US/guide/overlay.html)
- [KLineChart repository](https://github.com/klinecharts/KLineChart)

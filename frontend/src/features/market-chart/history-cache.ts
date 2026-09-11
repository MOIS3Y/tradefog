/** Bounded, session-local candle history; never an authority for live prices. */
import type { Candle, CandlePage, MarketInstrument } from "./types";

interface Entry {
  page: CandlePage;
  touched: number;
}

/** Compare all chart fields without constructing numeric wrappers. */
export function sameCandle(a: Candle, b: Candle): boolean {
  return (
    a.timestamp === b.timestamp &&
    a.open === b.open &&
    a.high === b.high &&
    a.low === b.low &&
    a.close === b.close &&
    a.volume === b.volume &&
    a.turnover === b.turnover
  );
}

/** Keep complete cached ranges so eviction never corrupts a history cursor. */
export class HistoryCache {
  private entries = new Map<string, Entry>();
  version = 0;

  constructor(
    private readonly ttl = 600_000,
    private readonly maxEntries = 8,
    private readonly maxBars = 20_000,
  ) {}

  /** Namespace public data by provider, product, symbol and period. */
  key(
    provider: string,
    instrument: MarketInstrument,
    timeframe: string,
  ): string {
    return JSON.stringify([
      provider,
      instrument.product,
      instrument.symbol,
      timeframe,
    ]);
  }

  /** Clear on logout and invalidate writes from requests already in flight. */
  clear(): void {
    this.entries.clear();
    this.version++;
  }

  /** Reuse a range only while its idle lifetime remains valid. */
  get(key: string): CandlePage | undefined {
    this.prune();
    const entry = this.entries.get(key);
    if (!entry) return;
    entry.touched = Date.now();
    this.entries.delete(key);
    this.entries.set(key, entry);
    return entry.page;
  }

  /** Merge history or live bars, retaining the oldest page's continuation. */
  merge(key: string, page: CandlePage, version = this.version): void {
    if (version !== this.version) return;
    const previous = this.get(key);
    const bars = new Map(previous?.bars.map((bar) => [bar.timestamp, bar]));
    for (const bar of page.bars) bars.set(bar.timestamp, bar);
    const sorted = [...bars.values()].sort((a, b) => a.timestamp - b.timestamp);
    const extendsHistory =
      !previous ||
      (page.bars[0]?.timestamp ?? Infinity) <=
        (previous.bars[0]?.timestamp ?? Infinity);
    this.entries.delete(key);
    if (!sorted.length || sorted.length > this.maxBars) return;
    this.entries.set(key, {
      touched: Date.now(),
      page: {
        bars: sorted,
        hasMore: extendsHistory ? page.hasMore : previous!.hasMore,
      },
    });
    this.prune();
    let count = [...this.entries.values()].reduce(
      (sum, e) => sum + e.page.bars.length,
      0,
    );
    while (this.entries.size > this.maxEntries || count > this.maxBars) {
      const oldest = this.entries.entries().next().value;
      if (!oldest) break;
      count -= oldest[1].page.bars.length;
      this.entries.delete(oldest[0]);
    }
  }

  /** Expired inactive ranges are removed lazily on cache access. */
  private prune(): void {
    for (const [key, entry] of this.entries) {
      if (Date.now() - entry.touched >= this.ttl) this.entries.delete(key);
    }
  }
}

export const candleHistory = new HistoryCache();
window.addEventListener("tradefog:session-ended", () => candleHistory.clear());

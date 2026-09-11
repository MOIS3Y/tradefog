/** Independent candle and depth streams with session-local history reuse. */
import {
  MarketError,
  type Candle,
  type CandlePage,
  type MarketAdapter,
  type MarketInstrument,
  type OrderBook,
} from "./types";
import { candleHistory, sameCandle, type HistoryCache } from "./history-cache";
import { PollingLoop } from "./polling";

export interface FeedEvents {
  candles: (bars: Candle[]) => void;
  book: (book: OrderBook) => void;
  status: (panel: "chart" | "book", failed: boolean) => void;
  refreshing?: () => void;
}

/** Share cooldowns, not scheduling or cancellation, between market panels. */
export class MarketFeed {
  private active = false;
  private cooldownUntil = 0;
  private lastBar?: Candle;
  private visibleBook = true;
  private readonly chartLoop: PollingLoop;
  private readonly bookLoop: PollingLoop;
  private readonly cacheVersion: number;

  constructor(
    readonly adapter: MarketAdapter,
    readonly instrument: MarketInstrument,
    public timeframe: string,
    private readonly events: FeedEvents,
    private readonly cache: HistoryCache = candleHistory,
  ) {
    this.cacheVersion = cache.version;
    this.chartLoop = new PollingLoop(
      (signal) => this.recent(signal),
      () => this.cooldownUntil,
      adapter.refreshMs,
    );
    this.bookLoop = new PollingLoop(
      async (signal) => {
        if (!adapter.book) return;
        try {
          const book = await adapter.book(instrument, signal);
          signal.throwIfAborted();
          events.book(book);
          events.status("book", false);
        } catch (error) {
          if (!signal.aborted) this.failed("book", error);
          throw error;
        }
      },
      () => this.cooldownUntil,
      adapter.refreshMs,
    );
  }

  get bookVisible(): boolean {
    return this.visibleBook;
  }
  set bookVisible(value: boolean) {
    this.visibleBook = value;
    if (!value) this.bookLoop.pause();
    else if (this.active) this.bookLoop.resume();
  }

  /** Stop both streams when the market workspace is hidden or disposed. */
  pause(): void {
    this.active = false;
    this.chartLoop.pause();
    this.bookLoop.pause();
  }

  /** Retain cached drawings/history, but refresh prices on visibility return. */
  resume(): void {
    if (this.active) return;
    this.active = true;
    this.events.refreshing?.();
    this.chartLoop.resume();
    if (this.visibleBook) this.bookLoop.resume();
  }

  /** Restart only candle work; the book does not depend on chart period. */
  changeTimeframe(value: string): void {
    this.chartLoop.pause();
    this.timeframe = value;
    this.lastBar = undefined;
    this.events.refreshing?.();
    if (this.active) this.chartLoop.resume();
  }

  /** Load an initial cached range or a strictly older upstream page. */
  async history(before?: number): Promise<CandlePage> {
    if (!this.active) throw new DOMException("Market hidden", "AbortError");
    const key = this.cache.key(
      this.adapter.id,
      this.instrument,
      this.timeframe,
    );
    if (before === undefined) {
      const cached = this.cache.get(key);
      if (cached) {
        this.lastBar = cached.bars.at(-1);
        this.events.refreshing?.();
        return cached;
      }
    }
    if (Date.now() < this.cooldownUntil)
      throw new MarketError(this.cooldownUntil - Date.now());
    const signal = this.chartLoop.signal;
    try {
      const page = (await this.adapter.candles?.(this.instrument, {
        timeframe: this.timeframe,
        before,
        signal,
      })) ?? { bars: [], hasMore: false };
      signal.throwIfAborted();
      if (before === undefined || this.cache.get(key))
        this.cache.merge(key, page, this.cacheVersion);
      if (before === undefined) {
        this.lastBar = page.bars.at(-1);
        this.events.status("chart", false);
      }
      return page;
    } catch (error) {
      if (!signal.aborted) this.failed("chart", error);
      throw error;
    }
  }

  /** Throttling is shared; transient failures back off only their stream. */
  private failed(panel: "chart" | "book", error: unknown): void {
    if (error instanceof MarketError)
      this.cooldownUntil = Math.max(
        this.cooldownUntil,
        Date.now() + error.retryAfterMs,
      );
    this.events.status(panel, true);
  }

  /** Repair missed intervals before publishing only changed/new candles. */
  private async recent(signal: AbortSignal): Promise<void> {
    if (!this.adapter.candles || !this.lastBar) return;
    const last = this.lastBar;
    const timeframe = this.timeframe;
    const key = this.cache.key(this.adapter.id, this.instrument, timeframe);
    const collected = new Map<number, Candle>();
    let before: number | undefined;
    try {
      for (;;) {
        const { bars, hasMore } = await this.adapter.candles(this.instrument, {
          timeframe,
          before,
          signal,
          limit: before === undefined ? 2 : 500,
        });
        signal.throwIfAborted();
        for (const bar of bars) {
          if (bar.timestamp >= last.timestamp)
            collected.set(bar.timestamp, bar);
        }
        const first = bars[0]?.timestamp;
        if (!hasMore || first === undefined || first <= last.timestamp) break;
        if (before !== undefined && first >= before) throw new MarketError();
        before = first;
      }
      const bars = [...collected.values()].sort(
        (a, b) => a.timestamp - b.timestamp,
      );
      const changed = bars.filter((bar) => !sameCandle(bar, last));
      if (bars.length) {
        // Live updates never change the oldest cached page's continuation.
        const cached = this.cache.get(key);
        if (cached && changed.length)
          this.cache.merge(
            key,
            {
              bars,
              hasMore: cached.hasMore,
            },
            this.cacheVersion,
          );
        this.lastBar = bars.at(-1)!;
      }
      if (changed.length) this.events.candles(changed);
      this.events.status("chart", false);
    } catch (error) {
      if (!signal.aborted) this.failed("chart", error);
      throw error;
    }
  }
}

/** One cancellable refresh loop shared by candles and visible depth. */
import {
  MarketError,
  type Candle,
  type CandlePage,
  type MarketAdapter,
  type MarketInstrument,
  type OrderBook,
} from "./types";

export interface FeedEvents {
  candles: (bars: Candle[]) => void;
  book: (book: OrderBook) => void;
  status: (panel: "chart" | "book", failed: boolean) => void;
}

/** Serialize refresh cycles, retaining provider cooldowns across restarts. */
export class MarketFeed {
  private controller = new AbortController();
  private timer?: ReturnType<typeof setTimeout>;
  private active = false;
  private generation = 0;
  private failures = 0;
  private cooldownUntil = 0;
  private lastTimestamp?: number;
  bookVisible = true;

  constructor(
    readonly adapter: MarketAdapter,
    readonly instrument: MarketInstrument,
    public timeframe: string,
    private readonly events: FeedEvents,
  ) {}

  /** Abort old work; a new generation cannot accept old responses. */
  pause(): void {
    this.active = false;
    this.generation++;
    clearTimeout(this.timer);
    this.controller.abort();
    this.controller = new AbortController();
  }

  /** Resume immediately unless the provider imposed a cooldown. */
  resume(): void {
    if (this.active) return;
    this.active = true;
    this.schedule(0);
  }

  /** Change only chart context, retaining the IP-level cooldown. */
  changeTimeframe(value: string): void {
    const active = this.active;
    this.pause();
    this.timeframe = value;
    this.lastTimestamp = undefined;
    if (active) this.resume();
  }

  /** Load strictly older history without mutating the live cursor. */
  async history(before?: number): Promise<CandlePage> {
    if (!this.active) throw new DOMException("Market hidden", "AbortError");
    if (Date.now() < this.cooldownUntil)
      throw new MarketError(this.cooldownUntil - Date.now());
    const signal = this.controller.signal;
    try {
      const page = (await this.adapter.candles?.(this.instrument, {
        timeframe: this.timeframe,
        before,
        signal,
      })) ?? { bars: [], hasMore: false };
      signal.throwIfAborted();
      if (before === undefined)
        this.lastTimestamp = page.bars.at(-1)?.timestamp;
      if (before === undefined) this.events.status("chart", false);
      return page;
    } catch (error) {
      if (!signal.aborted) this.failed("chart", error);
      throw error;
    }
  }

  /** Record throttling separately from transient exponential backoff. */
  private failed(panel: "chart" | "book", error: unknown): void {
    if (error instanceof MarketError) {
      this.cooldownUntil = Math.max(
        this.cooldownUntil,
        Date.now() + error.retryAfterMs,
      );
    }
    this.events.status(panel, true);
  }

  /** Schedule only after completion; provider cooldown always wins. */
  private schedule(delay: number): void {
    if (!this.active) return;
    this.timer = setTimeout(
      () => void this.cycle(),
      Math.max(delay, this.cooldownUntil - Date.now()),
    );
  }

  /** Reconcile missed bars in bounded pages before publishing newer bars. */
  private async recent(signal: AbortSignal): Promise<void> {
    if (!this.adapter.candles || this.lastTimestamp === undefined) return;
    const collected: Candle[][] = [];
    let before: number | undefined;
    for (;;) {
      const { bars, hasMore } = await this.adapter.candles(this.instrument, {
        timeframe: this.timeframe,
        before,
        signal,
        limit: before === undefined ? 2 : 500,
      });
      signal.throwIfAborted();
      collected.unshift(
        bars.filter((bar) => bar.timestamp >= this.lastTimestamp!),
      );
      const first = bars[0]?.timestamp;
      if (!hasMore || first === undefined || first <= this.lastTimestamp) break;
      if (before !== undefined && first >= before) throw new MarketError();
      before = first;
    }
    const bars = collected.flat();
    if (bars.length) {
      this.events.candles(bars);
      this.lastTimestamp = bars.at(-1)!.timestamp;
    }
    this.events.status("chart", false);
  }

  /** Refresh panels independently so one failure cannot discard the other. */
  private async cycle(): Promise<void> {
    const generation = this.generation;
    const signal = this.controller.signal;
    const tasks: Promise<void>[] = [];
    if (this.adapter.candles && this.lastTimestamp !== undefined) {
      tasks.push(
        this.recent(signal).catch((error) => {
          if (!signal.aborted) this.failed("chart", error);
          throw error;
        }),
      );
    }
    if (this.adapter.book && this.bookVisible) {
      tasks.push(
        this.adapter
          .book(this.instrument, signal)
          .then((book) => {
            signal.throwIfAborted();
            this.events.book(book);
            this.events.status("book", false);
          })
          .catch((error) => {
            if (!signal.aborted) this.failed("book", error);
            throw error;
          }),
      );
    }
    const results = await Promise.allSettled(tasks);
    if (generation !== this.generation || !this.active) return;
    this.failures = results.some((r) => r.status === "rejected")
      ? Math.min(this.failures + 1, 4)
      : 0;
    // Faster normal polling must not shorten the existing error cooldowns.
    const delay = this.failures
      ? Math.max(this.adapter.refreshMs, 5000) * 2 ** this.failures
      : this.adapter.refreshMs;
    this.schedule(Math.min(delay, 60_000));
  }
}

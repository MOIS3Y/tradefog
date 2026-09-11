/** Bounded history and independent streams under slow and stale responses. */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { clearTokens } from "@/api/tokens";
import { MarketFeed } from "@/features/market-chart/feed";
import {
  HistoryCache,
  candleHistory,
} from "@/features/market-chart/history-cache";
import {
  MarketError,
  type Candle,
  type OrderBook,
  type CandlePage,
} from "@/features/market-chart/types";

const instrument = {
  symbol: "BTCUSDT",
  product: "spot",
  base: "BTC",
  quote: "USDT",
};
const bar = (timestamp: number, close = "2"): Candle => ({
  timestamp,
  open: "1",
  high: "3",
  low: "1",
  close,
  volume: "10",
});
const page = (times: number[], hasMore = true): CandlePage => ({
  bars: times.map((t) => bar(t)),
  hasMore,
});
const snapshot: OrderBook = { timestamp: 1, bids: [], asks: [] };

/** Controllable promises simulate exchanges that ignore browser cancellation. */
function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((done) => {
    resolve = done;
  });
  return { promise, resolve };
}

/** Each test owns its streams and cache, without relying on real time. */
function setup() {
  const candles = vi.fn().mockResolvedValue(page([1000], false));
  const book = vi.fn().mockResolvedValue(snapshot);
  const events = {
    candles: vi.fn(),
    book: vi.fn(),
    status: vi.fn(),
    refreshing: vi.fn(),
  };
  const adapter = {
    id: "bybit",
    name: "Bybit",
    timeframes: [],
    refreshMs: 1000,
    supports: () => true,
    link: () => "",
    candles,
    book,
  };
  const cache = new HistoryCache();
  const feed = new MarketFeed(adapter, instrument, "15m", events, cache);
  feeds.push(feed);
  return { feed, candles, book, events, cache };
}
const feeds: MarketFeed[] = [];
beforeEach(() => {
  vi.useFakeTimers();
});
afterEach(() => {
  for (const feed of feeds.splice(0)) feed.pause();
  vi.useRealTimers();
});

describe("independent market streams", () => {
  it("continues candle polling while one book request is stalled", async () => {
    const { feed, candles, book } = setup();
    const pending = deferred<OrderBook>();
    book.mockReturnValueOnce(pending.promise);
    feed.resume();
    await feed.history();
    await vi.advanceTimersByTimeAsync(3100);
    expect(book).toHaveBeenCalledTimes(1);
    expect(candles).toHaveBeenCalledTimes(5);
    pending.resolve(snapshot);
  });

  it("switches periods without aborting depth and ignores old history", async () => {
    const { feed, candles, book, events } = setup();
    const history = deferred<CandlePage>();
    const depth = deferred<OrderBook>();
    candles.mockReturnValueOnce(history.promise);
    book.mockReturnValueOnce(depth.promise);
    feed.resume();
    const old = feed.history();
    const rejection = expect(old).rejects.toMatchObject({ name: "AbortError" });
    await vi.advanceTimersByTimeAsync(0);
    const signal = book.mock.calls[0]![1] as AbortSignal;
    feed.changeTimeframe("1h");
    expect(signal.aborted).toBe(false);
    history.resolve(page([9999]));
    await rejection;
    await feed.history();
    depth.resolve(snapshot);
    await vi.advanceTimersByTimeAsync(0);
    expect(events.book).toHaveBeenCalledOnce();
    expect(candles.mock.calls.at(-1)![1].timeframe).toBe("1h");
  });

  it("reuses history on return and only publishes changed candles", async () => {
    const { feed, candles, events } = setup();
    feed.resume();
    await feed.history();
    await vi.advanceTimersByTimeAsync(0);
    expect(events.candles).not.toHaveBeenCalled();
    feed.changeTimeframe("1h");
    await feed.history();
    feed.changeTimeframe("15m");
    const calls = candles.mock.calls.length;
    expect((await feed.history()).bars).toEqual([bar(1000)]);
    expect(candles).toHaveBeenCalledTimes(calls);
    candles.mockResolvedValueOnce({
      bars: [bar(1000, "3"), bar(2000)],
      hasMore: false,
    });
    await vi.advanceTimersByTimeAsync(0);
    expect(events.candles).toHaveBeenCalledWith([bar(1000, "3"), bar(2000)]);
    expect(events.refreshing).toHaveBeenCalled();
  });

  it("shares server cooldown but not transient failure backoff", async () => {
    const { feed, candles, book } = setup();
    feed.resume();
    await feed.history();
    book.mockRejectedValueOnce(new Error("slow depth"));
    await vi.advanceTimersByTimeAsync(3000);
    expect(candles).toHaveBeenCalledTimes(5);
    expect(book).toHaveBeenCalledOnce();
    candles.mockRejectedValueOnce(new MarketError(60_000));
    await vi.advanceTimersByTimeAsync(1000);
    const count = candles.mock.calls.length;
    await vi.advanceTimersByTimeAsync(59_999);
    expect(candles).toHaveBeenCalledTimes(count);
    expect(book).toHaveBeenCalledOnce();
    await vi.advanceTimersByTimeAsync(1);
    expect(book).toHaveBeenCalledTimes(2);
  });

  it("aborts only collapsed depth, then stops everything on pause", async () => {
    const { feed, candles, book, events } = setup();
    const pending = deferred<OrderBook>();
    book.mockReturnValueOnce(pending.promise);
    feed.resume();
    await feed.history();
    await vi.advanceTimersByTimeAsync(0);
    feed.bookVisible = false;
    expect(book.mock.calls[0]![1].aborted).toBe(true);
    pending.resolve(snapshot);
    await vi.advanceTimersByTimeAsync(2000);
    expect(events.book).not.toHaveBeenCalled();
    expect(candles.mock.calls.length).toBeGreaterThan(2);
    feed.pause();
    const count = candles.mock.calls.length;
    await vi.advanceTimersByTimeAsync(30_000);
    expect(candles).toHaveBeenCalledTimes(count);
  });
});

describe("session history cache", () => {
  it("merges ordered unique ranges and retains the oldest cursor", () => {
    const cache = new HistoryCache();
    cache.merge("a", page([2000, 3000]));
    cache.merge("a", page([1000, 2000], false));
    cache.merge("a", { bars: [bar(3000, "3"), bar(4000)], hasMore: true });
    expect(cache.get("a")).toEqual({
      bars: [bar(1000), bar(2000), bar(3000, "3"), bar(4000)],
      hasMore: false,
    });
  });

  it("bounds idle TTL, LRU count and total candles", () => {
    const cache = new HistoryCache(1000, 2, 4);
    cache.merge("a", page([1, 2]));
    cache.merge("b", page([1, 2]));
    cache.get("a");
    cache.merge("c", page([1]));
    expect(cache.get("b")).toBeUndefined();
    cache.merge("a", page([3, 4, 5]));
    expect(cache.get("a")).toBeUndefined();
    vi.advanceTimersByTime(1000);
    expect(cache.get("c")).toBeUndefined();
  });

  it("separates instruments, products and periods and clears on logout", () => {
    const key = candleHistory.key("bybit", instrument, "15m");
    expect(candleHistory.key("bybit", instrument, "1h")).not.toBe(key);
    expect(candleHistory.key("other", instrument, "15m")).not.toBe(key);
    expect(
      candleHistory.key(
        "bybit",
        { ...instrument, product: "perpetual_future" },
        "15m",
      ),
    ).not.toBe(key);
    const version = candleHistory.version;
    candleHistory.merge(key, page([1]));
    clearTokens();
    candleHistory.merge(key, page([2]), version);
    expect(candleHistory.get(key)).toBeUndefined();
  });
});

/** Provider contracts, polling safety and local annotation persistence. */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { bybit } from "@/features/market-chart/bybit";
import { cumulativeLevels } from "@/features/market-chart/transport";
import { reloadTokens, setTokens } from "@/api/tokens";
import {
  browserDrawings,
  sanitizeDrawings,
} from "@/features/market-chart/drawings";
import { MarketFeed } from "@/features/market-chart/feed";
import { candleHistory } from "@/features/market-chart/history-cache";
import { resolveMarket } from "@/features/market-chart/registry";
import {
  MarketError,
  type Candle,
  type MarketAdapter,
  type MarketInstrument,
} from "@/features/market-chart/types";

const instrument: MarketInstrument = {
  symbol: "BTCUSDT",
  product: "spot",
  base: "BTC",
  quote: "USDT",
};

/** Build one normalized candle without testing exchange implementation. */
function bar(timestamp: number): Candle {
  return { timestamp, open: "1", high: "2", low: "1", close: "2" };
}

beforeEach(() => {
  vi.useFakeTimers();
  localStorage.clear();
  reloadTokens();
  candleHistory.clear();
});
afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

describe("public provider adapter", () => {
  it("accumulates normalized book depth with exact decimals", () => {
    expect(
      cumulativeLevels([
        { price: "2", size: "0.1" },
        { price: "1", size: "0.2" },
      ]),
    ).toEqual([
      { price: "2", size: "0.1", total: "0.1" },
      { price: "1", size: "0.2", total: "0.3" },
    ]);
  });
  it("uses authenticated app candles and the exclusive server cursor", async () => {
    setTokens({
      access_token: "token",
      refresh_token: "refresh",
      token_type: "bearer",
    });
    const fetcher = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
          bars: [
            { ...bar(1000), volume: "0.000000000000000001", turnover: null },
          ],
          has_more: true,
          received_at: 2000,
        }),
        { headers: { "Content-Type": "application/json" } },
      ),
    );
    vi.stubGlobal("fetch", fetcher);
    const result = await bybit.candles!(instrument, {
      timeframe: "15m",
      before: 2000,
      signal: new AbortController().signal,
    });
    const request = fetcher.mock.calls[0]![0] as Request;
    const url = new URL(request.url);
    expect(url.pathname).toBe("/api/v1/venues/bybit/public/klines");
    expect(url.origin).toBe(window.location.origin);
    expect(url.searchParams.get("before")).toBe("2000");
    expect(url.searchParams.get("timeframe")).toBe("15m");
    expect(request.headers.get("Authorization")).toBe("Bearer token");
    expect(result.bars[0]?.volume).toBe("0.000000000000000001");
    expect(result.hasMore).toBe(true);
  });
  it("respects server cooldowns", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(null, {
          status: 503,
          headers: { "Retry-After": "600" },
        }),
      ),
    );
    await expect(
      bybit.book!(instrument, new AbortController().signal),
    ).rejects.toMatchObject({ retryAfterMs: 600000 });
  });

  it("does not infer chart capability from ATR support", () => {
    expect(resolveMarket("bybit", instrument)).toBe(bybit);
    expect(resolveMarket("binance", instrument)).toBeUndefined();
    expect(resolveMarket("none", instrument)).toBeUndefined();
    expect(
      resolveMarket("bybit", { ...instrument, product: "cash_equity" }),
    ).toBeUndefined();
    expect(
      resolveMarket("bybit", {
        ...instrument,
        product: "perpetual_future",
        quote: "USD",
      }),
    ).toBeUndefined();
    expect(resolveMarket("bybit", undefined)).toBeUndefined();
    expect(
      bybit.link({
        ...instrument,
        product: "perpetual_future",
        quote: "USDC",
        symbol: "BTCPERP",
      }),
    ).toBe("https://www.bybit.com/en/trade/futures/usdc/BTC-PERP");
  });
});

describe("market refresh lifecycle", () => {
  /** Construct an isolated feed with replaceable provider responses. */
  function setup() {
    const candles = vi
      .fn()
      .mockResolvedValue({ bars: [bar(1000)], hasMore: false });
    const book = vi
      .fn()
      .mockResolvedValue({ timestamp: 1000, bids: [], asks: [] });
    const adapter: MarketAdapter = { ...bybit, candles, book };
    const events = { candles: vi.fn(), book: vi.fn(), status: vi.fn() };
    const feed = new MarketFeed(adapter, instrument, "15", events);
    return { feed, candles, book, events };
  }

  it("never overlaps cycles and waits one second after completion", async () => {
    const { feed, book } = setup();
    let finish!: (value: unknown) => void;
    book.mockImplementationOnce(
      () =>
        new Promise((resolve) => {
          finish = resolve;
        }),
    );
    feed.resume();
    await vi.advanceTimersByTimeAsync(0);
    await vi.advanceTimersByTimeAsync(20_000);
    expect(book).toHaveBeenCalledTimes(1);
    finish({ timestamp: 1000, bids: [], asks: [] });
    await vi.advanceTimersByTimeAsync(999);
    expect(book).toHaveBeenCalledTimes(1);
    await vi.advanceTimersByTimeAsync(1);
    expect(book).toHaveBeenCalledTimes(2);
    feed.pause();
  });

  it("aborts hidden work, ignores late results and skips collapsed books", async () => {
    const { feed, book, events } = setup();
    let finish!: (value: unknown) => void;
    book.mockImplementationOnce(
      () =>
        new Promise((resolve) => {
          finish = resolve;
        }),
    );
    feed.resume();
    await vi.advanceTimersByTimeAsync(0);
    const signal = book.mock.calls[0]?.[1] as AbortSignal;
    feed.pause();
    expect(signal.aborted).toBe(true);
    finish({ timestamp: 1000, bids: [], asks: [] });
    await vi.advanceTimersByTimeAsync(30_000);
    expect(events.book).not.toHaveBeenCalled();
    await expect(feed.history()).rejects.toMatchObject({ name: "AbortError" });
    feed.bookVisible = false;
    feed.resume();
    await vi.advanceTimersByTimeAsync(10_000);
    expect(book).toHaveBeenCalledTimes(1);
    feed.pause();
  });

  it("backs off failures and returns to normal cadence after recovery", async () => {
    const { feed, book, events } = setup();
    book.mockRejectedValueOnce(new Error("offline"));
    feed.resume();
    await vi.advanceTimersByTimeAsync(0);
    expect(events.status).toHaveBeenCalledWith("book", true);
    await vi.advanceTimersByTimeAsync(9999);
    expect(book).toHaveBeenCalledTimes(1);
    await vi.advanceTimersByTimeAsync(1);
    expect(book).toHaveBeenCalledTimes(2);
    await vi.advanceTimersByTimeAsync(1000);
    expect(book).toHaveBeenCalledTimes(3);
    feed.pause();
  });

  it("preserves long error backoff despite one-second normal polling", async () => {
    const { feed, book } = setup();
    book.mockRejectedValue(new Error("offline"));
    feed.resume();
    await vi.advanceTimersByTimeAsync(0);
    for (const delay of [10_000, 20_000, 40_000, 60_000, 60_000]) {
      const calls = book.mock.calls.length;
      await vi.advanceTimersByTimeAsync(delay - 1);
      expect(book).toHaveBeenCalledTimes(calls);
      await vi.advanceTimersByTimeAsync(1);
      expect(book).toHaveBeenCalledTimes(calls + 1);
    }
    feed.pause();
  });

  it("retains cooldown across timeframe changes and manual resume", async () => {
    const { feed, book } = setup();
    book.mockRejectedValueOnce(new MarketError(600_000));
    feed.resume();
    await vi.advanceTimersByTimeAsync(0);
    feed.changeTimeframe("D");
    feed.pause();
    feed.resume();
    await expect(feed.history()).rejects.toMatchObject({
      retryAfterMs: 600_000,
    });
    await vi.advanceTimersByTimeAsync(599_999);
    expect(book).toHaveBeenCalledTimes(1);
    await vi.advanceTimersByTimeAsync(1);
    expect(book).toHaveBeenCalledTimes(2);
    feed.pause();
  });

  it("reconciles missed candles in order before updating the latest bar", async () => {
    const { feed, candles, events } = setup();
    feed.bookVisible = false;
    feed.resume();
    await feed.history();
    candles.mockResolvedValueOnce({
      bars: [bar(3000), bar(4000)],
      hasMore: true,
    });
    candles.mockResolvedValueOnce({
      bars: [bar(1000), bar(2000)],
      hasMore: false,
    });
    await vi.advanceTimersByTimeAsync(0);
    expect(
      events.candles.mock.calls[0]?.[0].map((item: Candle) => item.timestamp),
    ).toEqual([2000, 3000, 4000]);
    expect(candles.mock.calls[2]?.[1].before).toBe(3000);
    feed.pause();
  });
});

describe("local drawing store", () => {
  it("persists only supported anchors across reloads, scoped by key", () => {
    const drawings = [
      {
        name: "segment",
        points: [
          { timestamp: 1000, value: 42 },
          { timestamp: 2000, value: 43 },
        ],
        secretRuntime: "ignored",
      },
    ];
    expect(browserDrawings.save("user:1:trade:2:instrument:3", drawings)).toBe(
      true,
    );
    expect(browserDrawings.load("user:1:trade:2:instrument:3")).toEqual(
      sanitizeDrawings(drawings),
    );
    expect(browserDrawings.load("user:2:trade:2:instrument:3")).toEqual([]);
    expect(localStorage.getItem("user:1:trade:2:instrument:3")).not.toContain(
      "secretRuntime",
    );
    expect(sanitizeDrawings([{ name: "unknown", points: [] }])).toEqual([]);
    localStorage.setItem("broken", "not json");
    expect(browserDrawings.load("broken")).toEqual([]);
  });

  it("bounds drawings and treats storage failure as best effort", () => {
    const drawing = {
      name: "horizontalStraightLine",
      points: [{ timestamp: 1000, value: 42 }],
    };
    expect(sanitizeDrawings(Array(101).fill(drawing))).toHaveLength(100);
    vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
      throw new Error("quota");
    });
    expect(browserDrawings.save("key", [drawing])).toBe(false);
  });
});

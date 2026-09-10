/** Exercise canvas integration without depending on canvas rasterization. */
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { createApp, h, nextTick, reactive, type App } from "vue";
import type { DataLoader, SymbolInfo } from "klinecharts";
import { i18n } from "@/i18n";
import MarketPanel from "@/features/market-chart/MarketPanel.vue";
import { bybit } from "@/features/market-chart/bybit";
import ChartCanvas from "@/features/market-chart/ChartCanvas.vue";
import { MarketFeed } from "@/features/market-chart/feed";

const fake = vi.hoisted(() => ({
  loader: undefined as DataLoader | undefined,
  push: vi.fn(),
  init: vi.fn(),
  dispose: vi.fn(),
  overlays: vi.fn(),
  styles: vi.fn(),
  separator: vi.fn(),
  symbol: { ticker: "", pricePrecision: 0, volumePrecision: 0 },
  setSymbol: vi.fn(),
}));
vi.mock("klinecharts", () => ({
  init: fake.init,
  dispose: fake.dispose,
  registerLocale: vi.fn(),
}));
let app: App | undefined;
let root: HTMLDivElement;

/** Flush async import, Vue rendering and provider resolution. */
async function flush(): Promise<void> {
  for (let i = 0; i < 10; i++) {
    await nextTick();
    await vi.advanceTimersByTimeAsync(0);
  }
}

beforeEach(() => {
  vi.useFakeTimers();
  fake.symbol = { ticker: "", pricePrecision: 0, volumePrecision: 0 };
  fake.setSymbol.mockImplementation((symbol: SymbolInfo) => {
    fake.symbol = { ...symbol };
  });
  vi.stubGlobal(
    "ResizeObserver",
    class {
      observe(): void {}
      disconnect(): void {}
    },
  );
  fake.init.mockReturnValue({
    setStyles: fake.styles,
    setThousandsSeparator: fake.separator,
    setTimezone: vi.fn(),
    setSymbol: fake.setSymbol,
    getSymbol: () => fake.symbol,
    setLocale: vi.fn(),
    getOverlays: () => [],
    createOverlay: fake.overlays,
    setDataLoader: (loader: DataLoader) => {
      fake.loader = loader;
    },
    setPeriod: () => {
      void fake.loader?.getBars({
        type: "init",
        timestamp: null,
        symbol: { ticker: "BTCUSDT", pricePrecision: 2, volumePrecision: 6 },
        period: { span: 15, type: "minute" },
        callback: () => {
          fake.loader?.subscribeBar?.({
            symbol: {
              ticker: "BTCUSDT",
              pricePrecision: 2,
              volumePrecision: 6,
            },
            period: { span: 15, type: "minute" },
            callback: fake.push,
          });
        },
      });
    },
    getConvertPictureUrl: () => "data:image/png;base64,aGVsbG8=",
  });
  root = document.createElement("div");
  root.className = "tf-app";
  document.body.append(root);
});
afterEach(() => {
  app?.unmount();
  root.remove();
  vi.useRealTimers();
  vi.unstubAllGlobals();
  vi.clearAllMocks();
  Reflect.deleteProperty(HTMLElement.prototype, "requestFullscreen");
  Reflect.deleteProperty(document, "exitFullscreen");
  Reflect.deleteProperty(document, "fullscreenElement");
});

it("switches candle rendering without rebuilding or refetching history", async () => {
  const candles = vi.fn().mockResolvedValue({ bars: [], hasMore: false });
  const instrument = {
    symbol: "BTCUSDT",
    product: "spot",
    base: "BTC",
    quote: "USDT",
  };
  const feed = new MarketFeed(
    { ...bybit, candles, book: undefined },
    instrument,
    "15",
    { candles: vi.fn(), book: vi.fn(), status: vi.fn() },
  );
  const state = reactive<{ type: "candle_solid" | "ohlc" | "area" }>({
    type: "candle_solid",
  });
  feed.resume();
  app = createApp({
    render: () =>
      h(ChartCanvas, {
        feed,
        timeframe: bybit.timeframes[2]!,
        storageKey: "type-test",
        chartType: state.type,
      }),
  });
  app.use(i18n).mount(root);
  await flush();
  const initialRequests = candles.mock.calls.length;
  expect(fake.separator).toHaveBeenCalledWith({ sign: "\u00a0" });
  for (const type of ["ohlc", "area", "candle_solid"] as const) {
    state.type = type;
    await flush();
    expect(fake.styles).toHaveBeenLastCalledWith({ candle: { type } });
  }
  expect(fake.init).toHaveBeenCalledTimes(1);
  expect(candles).toHaveBeenCalledTimes(initialRequests);
  expect(fake.dispose).not.toHaveBeenCalled();
  feed.pause();
});

it("learns precision from history and live candles without resetting data", async () => {
  const bar = {
    timestamp: 1000,
    open: "78350.10",
    high: "78351.125",
    low: "78349",
    close: "78350.2",
    volume: "0.001200",
  };
  const candles = vi
    .fn()
    .mockResolvedValueOnce({ bars: [bar], hasMore: false })
    .mockResolvedValue({ bars: [bar], hasMore: false });
  const feed = new MarketFeed(
    { ...bybit, candles, book: undefined },
    { symbol: "BTCUSDT", product: "spot", base: "BTC", quote: "USDT" },
    "15",
    { candles: (bars) => canvas?.update(bars), book: vi.fn(), status: vi.fn() },
  );
  let canvas: InstanceType<typeof ChartCanvas> | null = null;
  feed.resume();
  app = createApp({
    render: () =>
      h(ChartCanvas, {
        ref: (instance) => {
          canvas = instance as InstanceType<typeof ChartCanvas>;
        },
        feed,
        timeframe: bybit.timeframes[2]!,
        storageKey: "precision-test",
      }),
  });
  app.use(i18n).mount(root);
  await flush();
  expect(fake.symbol).toMatchObject({ pricePrecision: 3, volumePrecision: 4 });
  candles.mockResolvedValue({
    bars: [{ ...bar, close: "78350.12345" }],
    hasMore: false,
  });
  await vi.advanceTimersByTimeAsync(1000);
  expect(fake.symbol).toMatchObject({ pricePrecision: 5, volumePrecision: 4 });
  candles.mockResolvedValue({
    bars: [{ ...bar, open: "1", high: "2", low: "1", close: "2", volume: "1" }],
    hasMore: false,
  });
  await vi.advanceTimersByTimeAsync(1000);
  expect(fake.symbol).toMatchObject({ pricePrecision: 5, volumePrecision: 4 });
  expect(fake.init).toHaveBeenCalledTimes(1);
  expect(fake.setSymbol).toHaveBeenCalledTimes(1);
  feed.pause();
});

it("switches book sides locally while preserving depth and polling", async () => {
  const book = vi.fn().mockResolvedValue({
    timestamp: 1000,
    bids: [{ price: "100", size: "0.1", total: "0.1" }],
    asks: [{ price: "101", size: "0.2", total: "0.2" }],
  });
  app = createApp(MarketPanel, {
    adapter: { ...bybit, candles: undefined, book },
    instrument: {
      symbol: "BTCUSDT",
      product: "spot",
      base: "BTC",
      quote: "USDT",
    },
    storageKey: "book-test",
    saveSnapshot: vi.fn(),
  });
  app.use(i18n).mount(root);
  await flush();
  expect(root.querySelectorAll(".market-book__row")).toHaveLength(2);
  expect(
    root
      .querySelector(".market-book__bids .market-book__row")
      ?.getAttribute("style"),
  ).toContain("50%");
  const count = book.mock.calls.length;
  const bids = [
    ...root.querySelectorAll<HTMLButtonElement>(".market-book__modes button"),
  ].find((button) => button.textContent?.trim() === "Bids")!;
  bids.click();
  await flush();
  expect(root.querySelector(".market-book__asks")).toBeNull();
  expect(root.querySelector(".market-book__bids")).not.toBeNull();
  expect(book).toHaveBeenCalledTimes(count);
  root.querySelector<HTMLButtonElement>(".market-book__toggle")!.click();
  await flush();
  await vi.advanceTimersByTimeAsync(2000);
  expect(book).toHaveBeenCalledTimes(count);
});

it("keeps the chart mounted through full screen and browser-initiated exit", async () => {
  let fullscreenElement: Element | null = null;
  Object.defineProperty(document, "fullscreenElement", {
    configurable: true,
    get: () => fullscreenElement,
  });
  const request = vi.fn(async function (this: HTMLElement) {
    fullscreenElement = this;
    document.dispatchEvent(new Event("fullscreenchange"));
  });
  Object.defineProperty(HTMLElement.prototype, "requestFullscreen", {
    configurable: true,
    value: request,
  });
  Object.defineProperty(document, "exitFullscreen", {
    configurable: true,
    value: vi.fn(async () => {
      fullscreenElement = null;
      document.dispatchEvent(new Event("fullscreenchange"));
    }),
  });
  const book = vi
    .fn()
    .mockResolvedValue({ timestamp: 1000, asks: [], bids: [] });
  app = createApp({
    render: () =>
      h(MarketPanel, {
        adapter: {
          ...bybit,
          candles: vi.fn().mockResolvedValue({ bars: [], hasMore: false }),
          book,
        },
        instrument: {
          symbol: "BTCUSDT",
          product: "spot",
          base: "BTC",
          quote: "USDT",
        },
        storageKey: "fullscreen-test",
        saveSnapshot: vi.fn(),
      }),
  });
  app.use(i18n).mount(root);
  await flush();
  root
    .querySelector<HTMLButtonElement>('button[aria-label="Full screen"]')!
    .click();
  await flush();
  expect(fullscreenElement).toBe(root.querySelector(".market-chart"));
  expect(document.fullscreenElement?.querySelector(".market-book")).toBeNull();
  const requests = book.mock.calls.length;
  await vi.advanceTimersByTimeAsync(1000);
  expect(book).toHaveBeenCalledTimes(requests);
  expect(
    root
      .querySelector('button[aria-label="Exit full screen"]')
      ?.getAttribute("aria-pressed"),
  ).toBe("true");
  // The browser emits this same event when the user presses Escape.
  await document.exitFullscreen();
  await flush();
  expect(root.querySelector('button[aria-label="Full screen"]')).not.toBeNull();
  await vi.advanceTimersByTimeAsync(1000);
  expect(book.mock.calls.length).toBeGreaterThan(requests);
  expect(fake.init).toHaveBeenCalledTimes(1);
  request.mockRejectedValueOnce(new Error("Denied"));
  root
    .querySelector<HTMLButtonElement>('button[aria-label="Full screen"]')!
    .click();
  await flush();
  expect(root.textContent).toContain("Full screen is unavailable");
});

it("updates candles in place and retries screenshot upload without removing drawings", async () => {
  const candles = vi.fn().mockResolvedValue({
    bars: [{ timestamp: 1000, open: "1", high: "2", low: "1", close: "2" }],
    hasMore: false,
  });
  const saveSnapshot = vi
    .fn()
    .mockRejectedValueOnce(new Error("offline"))
    .mockResolvedValue(undefined);
  app = createApp({
    render: () =>
      h(MarketPanel, {
        adapter: { ...bybit, candles, book: undefined },
        instrument: {
          symbol: "BTCUSDT",
          product: "spot",
          base: "BTC",
          quote: "USDT",
        },
        storageKey: "test-drawings",
        saveSnapshot,
      }),
  });
  app.use(i18n).mount(root);
  await flush();
  expect(fake.init).toHaveBeenCalledTimes(1);
  expect(root.querySelector(".market-book")).toBeNull();
  await vi.advanceTimersByTimeAsync(1000);
  expect(fake.push).toHaveBeenCalledWith({
    timestamp: 1000,
    open: 1,
    high: 2,
    low: 1,
    close: 2,
    volume: undefined,
    turnover: undefined,
  });
  expect(fake.init).toHaveBeenCalledTimes(1);
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({
      blob: () => Promise.resolve(new Blob(["image"], { type: "image/png" })),
    }),
  );
  const button = root.querySelector<HTMLButtonElement>(
    'button[aria-label="Save snapshot to journal"]',
  )!;
  expect(button.disabled).toBe(false);
  button.click();
  await flush();
  expect(root.textContent).toContain("Snapshot upload failed");
  button.click();
  await flush();
  expect(saveSnapshot).toHaveBeenCalledTimes(2);
  expect(saveSnapshot.mock.calls[0]?.[0]).toBeInstanceOf(File);
  expect(root.textContent).toContain("Snapshot saved to journal");
  expect(fake.init).toHaveBeenCalledTimes(1);
});

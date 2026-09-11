/** Market rendering preserves canvas identity and avoids snapshot rework. */
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { createApp, h, nextTick, ref, type App } from "vue";
import type { DataLoader, Period } from "klinecharts";
import { i18n } from "@/i18n";
import ChartCanvas from "@/features/market-chart/ChartCanvas.vue";
import OrderBookPanel from "@/features/market-chart/OrderBookPanel.vue";
import type { MarketFeed } from "@/features/market-chart/feed";
import type { CandlePage, Timeframe } from "@/features/market-chart/types";
import * as bookFormatting from "@/features/market-chart/book-format";

const library = vi.hoisted(() => {
  const state: { loader?: DataLoader } = {};
  const callback = vi.fn();
  const symbol = { ticker: "BTCUSDT", pricePrecision: 0, volumePrecision: 0 };
  const chart = {
    createIndicator: vi.fn(),
    removeIndicator: vi.fn(),
    setStyles: vi.fn(),
    setLocale: vi.fn(),
    setThousandsSeparator: vi.fn(),
    setTimezone: vi.fn(),
    setSymbol: vi.fn(),
    getSymbol: () => symbol,
    setDataLoader: (loader: DataLoader) => {
      state.loader = loader;
    },
    setPeriod: vi.fn((period: Period) => {
      state.loader!.getBars({
        type: "init",
        symbol,
        period,
        timestamp: null,
        callback,
      });
    }),
    createOverlay: vi.fn(),
    resize: vi.fn(),
  };
  return { state, callback, chart, init: vi.fn(() => chart), dispose: vi.fn() };
});
vi.mock("klinecharts", () => ({
  init: library.init,
  dispose: library.dispose,
  registerLocale: vi.fn(),
}));
let app: App | undefined;
beforeEach(() => {
  vi.clearAllMocks();
  document.body.innerHTML = '<div id="root" class="tf-app"></div>';
  i18n.global.locale.value = "en";
  vi.stubGlobal(
    "ResizeObserver",
    class {
      observe() {}
      disconnect() {}
    },
  );
});
afterEach(() => {
  app?.unmount();
  app = undefined;
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

it("keeps one canvas and restores drawings once across periods", async () => {
  const indicators = ref(["VOL"]);
  const page: CandlePage = {
    bars: [{ timestamp: 1, open: "1", high: "2", low: "1", close: "2" }],
    hasMore: false,
  };
  const history = vi.fn().mockResolvedValue(page);
  const feed = {
    instrument: { symbol: "BTCUSDT" },
    history,
  } as unknown as MarketFeed;
  const period = ref<Timeframe>({
    value: "15m",
    label: "15m",
    span: 15,
    unit: "minute",
  });
  app = createApp({
    render: () =>
      h(ChartCanvas, {
        feed,
        timeframe: period.value,
        storageKey: "test",
        indicators: indicators.value,
      }),
  });
  app.use(i18n).mount("#root");
  await vi.waitFor(() => expect(library.callback).toHaveBeenCalledOnce());
  const canvas = document.querySelector(".market-chart__canvas");
  indicators.value = ["VOL", "MA", "RSI"];
  await nextTick();
  expect(library.chart.createIndicator).toHaveBeenCalledTimes(3);
  expect(library.chart.createIndicator).toHaveBeenCalledWith(
    { name: "MA", paneId: "candle_pane" },
    true,
  );
  indicators.value = ["VOL", "RSI"];
  await nextTick();
  expect(library.chart.removeIndicator).toHaveBeenCalledWith({ name: "MA" });
  expect(history).toHaveBeenCalledOnce();
  period.value = { value: "1h", label: "1h", span: 1, unit: "hour" };
  await nextTick();
  await vi.waitFor(() => expect(library.callback).toHaveBeenCalledTimes(2));
  expect(library.init).toHaveBeenCalledOnce();
  expect(library.dispose).not.toHaveBeenCalled();
  expect(library.chart.createOverlay).toHaveBeenCalledOnce();
  expect(document.querySelector(".market-chart__canvas")).toBe(canvas);
  expect(library.chart.setPeriod).toHaveBeenLastCalledWith({
    span: 1,
    type: "hour",
  });
  app.unmount();
  app = undefined;
  expect(library.dispose).toHaveBeenCalledOnce();
});

it("rejects a late loader callback from the previous period", async () => {
  let finish!: (value: CandlePage) => void;
  const history = vi
    .fn()
    .mockReturnValueOnce(
      new Promise<CandlePage>((resolve) => {
        finish = resolve;
      }),
    )
    .mockResolvedValue({ bars: [], hasMore: false });
  const feed = {
    instrument: { symbol: "BTCUSDT" },
    history,
  } as unknown as MarketFeed;
  const period = ref<Timeframe>({
    value: "15m",
    label: "15m",
    span: 15,
    unit: "minute",
  });
  app = createApp({
    render: () =>
      h(ChartCanvas, { feed, timeframe: period.value, storageKey: "late" }),
  });
  app.use(i18n).mount("#root");
  await vi.waitFor(() => expect(history).toHaveBeenCalledOnce());
  period.value = { value: "1h", label: "1h", span: 1, unit: "hour" };
  await nextTick();
  await vi.waitFor(() => expect(library.callback).toHaveBeenCalledOnce());
  finish({ bars: [], hasMore: false });
  await nextTick();
  expect(library.callback).toHaveBeenCalledOnce();
});

it("aligns prices by grouping precision and retains exact amount tooltips", async () => {
  app = createApp(OrderBookPanel, {
    hasChart: true,
    exchangeName: "Bybit",
    exchangeUrl: "https://example.com",
    base: "BTC",
    quote: "USDT",
  });
  const panel = app.use(i18n).mount("#root") as InstanceType<
    typeof OrderBookPanel
  >;
  panel.update({
    timestamp: 1,
    asks: [{ price: "77118.1", size: "115740.671234", total: "115740.671234" }],
    bids: [{ price: "77118", size: "0.000123456789", total: "0.000123456789" }],
  });
  await nextTick();
  const bids = document.querySelectorAll(
    ".market-book__bids .market-book__row span",
  );
  const asks = document.querySelectorAll(
    ".market-book__asks .market-book__row span",
  );
  expect(bids[0]?.textContent).toBe("77118.0");
  expect(asks[0]?.textContent).toBe("77118.1");
  expect(bids[1]?.textContent).toBe("0.0001235");
  expect(bids[1]?.getAttribute("title")).toBe("0.000123456789");
  expect(asks[2]?.textContent).toBe("115.74K");
  expect(asks[2]?.getAttribute("title")).toBe("115740.671234");
});

it("does not reformat unchanged depth on successful receipts or side switches", async () => {
  const formatting = vi.spyOn(bookFormatting, "formatBookAmount");
  app = createApp(OrderBookPanel, {
    hasChart: true,
    exchangeName: "Bybit",
    exchangeUrl: "https://example.com",
    base: "BTC",
    quote: "USDT",
  });
  const panel = app.use(i18n).mount("#root") as InstanceType<
    typeof OrderBookPanel
  >;
  const book = {
    timestamp: 1,
    asks: [{ price: "2.00", size: "0.20", total: "0.20" }],
    bids: [{ price: "1.00", size: "0.10", total: "0.10" }],
  };
  panel.update(book);
  panel.status(false);
  await nextTick();
  const count = formatting.mock.calls.length;
  panel.update({ ...book, timestamp: 2 });
  panel.status(false);
  await nextTick();
  expect(formatting).toHaveBeenCalledTimes(count);
  document
    .querySelectorAll<HTMLButtonElement>(".market-book__modes button")[2]!
    .click();
  await nextTick();
  expect(formatting).toHaveBeenCalledTimes(count);
  expect(document.querySelectorAll(".market-book__row")).toHaveLength(1);
  const unit = document.querySelector<HTMLButtonElement>(".market-book__unit")!;
  unit.click();
  await nextTick();
  expect(unit.textContent).toContain("USDT");
  expect(
    document.querySelector(".market-book__row span:nth-child(2)")?.textContent,
  ).toBe("0.4");
  const quoteCount = formatting.mock.calls.length;
  panel.update({ ...book, timestamp: 3 });
  panel.status(false);
  await nextTick();
  expect(formatting).toHaveBeenCalledTimes(quoteCount);
  unit.click();
  await nextTick();
  expect(unit.textContent).toContain("BTC");
  expect(
    document.querySelector(".market-book__row span:nth-child(2)")?.textContent,
  ).toBe("0.2");
  panel.updatePrice("100");
  await nextTick();
  expect(document.querySelector(".market-book__last")?.textContent).toContain(
    "100",
  );
  panel.updatePrice("101");
  await nextTick();
  expect(document.querySelector(".market-book__last.is-up")).not.toBeNull();
  panel.updatePrice("99");
  await nextTick();
  expect(document.querySelector(".market-book__last.is-down")).not.toBeNull();
  panel.status(true);
  await nextTick();
  expect(document.body.textContent).toContain("Last updated:");
  expect(document.querySelector("time")).toBeNull();
});

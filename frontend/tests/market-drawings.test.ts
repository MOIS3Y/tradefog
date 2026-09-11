/** Drawing lifecycle and storage cross the real canvas component boundary. */
import { afterEach, expect, it, vi } from "vitest";
import { createApp, h, nextTick, type App } from "vue";
import type { Overlay, OverlayCreate } from "klinecharts";
import ChartCanvas from "@/features/market-chart/ChartCanvas.vue";
import { browserDrawings } from "@/features/market-chart/drawings";
import { i18n } from "@/i18n";
import type { MarketFeed } from "@/features/market-chart/feed";

const mock = vi.hoisted(() => {
  const items: Overlay[] = [];
  return { items, create: vi.fn(), override: vi.fn(), remove: vi.fn() };
});
vi.mock("klinecharts", () => ({
  getOverlayClass: () => null,
  registerOverlay: vi.fn(),
  init: () => ({
    setStyles: vi.fn(),
    setLocale: vi.fn(),
    setTimezone: vi.fn(),
    setThousandsSeparator: vi.fn(),
    setSymbol: vi.fn(),
    setPeriod: vi.fn(),
    setDataLoader: vi.fn(),
    createIndicator: vi.fn(),
    resize: vi.fn(),
    getOverlays: () => mock.items,
    createOverlay: mock.create,
    overrideOverlay: mock.override,
    removeOverlay: mock.remove,
  }),
  dispose: vi.fn(),
  registerLocale: vi.fn(),
}));
let app: App | undefined;
afterEach(() => {
  app?.unmount();
  document.body.innerHTML = "";
  vi.unstubAllGlobals();
  vi.clearAllMocks();
});

/** Mount without network data; interactions operate on named overlay mocks. */
async function mountCanvas() {
  mock.items.splice(0);
  localStorage.clear();
  vi.stubGlobal(
    "ResizeObserver",
    class {
      observe() {}
      disconnect() {}
    },
  );
  mock.create.mockImplementation((input: OverlayCreate) => {
    const item = {
      ...input,
      id: String(mock.create.mock.calls.length),
      currentStep: 1,
      points: [],
    } as unknown as Overlay;
    mock.items.push(item);
    return item.id;
  });
  mock.override.mockImplementation((input: Partial<Overlay>) => {
    Object.assign(
      mock.items.find((item) => item.id === input.id)!,
      input,
    );
  });
  mock.remove.mockImplementation(({ id }: { id: string }) => {
    const index = mock.items.findIndex((item) => item.id === id);
    if (index >= 0) mock.items.splice(index, 1);
  });
  const root = document.createElement("div");
  document.body.append(root);
  let canvas: InstanceType<typeof ChartCanvas> | null = null;
  const textRequest = vi.fn();
  app = createApp({
    render: () =>
      h(ChartCanvas, {
        ref: (value) => {
          canvas = value as InstanceType<typeof ChartCanvas>;
        },
        feed: { instrument: { symbol: "BTCUSDT" } } as unknown as MarketFeed,
        timeframe: { value: "15m", label: "15m", span: 15, unit: "minute" },
        storageKey: "drawings",
        onTextRequest: textRequest,
      }),
  });
  app.use(i18n).mount(root);
  for (let i = 0; i < 10; i++) {
    await nextTick();
    await new Promise((resolve) => setTimeout(resolve, 0));
  }
  return { canvas: canvas!, textRequest };
}

/** Finish a one-point annotation with the same callback shape as KLineCharts. */
function finish(item: Overlay): void {
  item.currentStep = -1;
  item.points = [{ timestamp: 1000, value: 42 }];
  item.onDrawEnd?.({ overlay: item, chart: {} } as never);
}

it("creates, edits, colors and cancels text without losing saved drawings", async () => {
  const { canvas, textRequest } = await mountCanvas();
  canvas.draw("simpleAnnotation");
  const item = mock.items[0]!;
  finish(item);
  expect(textRequest).toHaveBeenCalledWith("");
  expect(browserDrawings.load("drawings")).toEqual([]);
  canvas.finishText("Analysis");
  item.onSelected?.({ overlay: item, chart: {} } as never);
  canvas.setColor("#f16e76");
  canvas.editText();
  expect(textRequest).toHaveBeenLastCalledWith("Analysis");
  canvas.finishText(null);
  expect(browserDrawings.load("drawings")[0]).toMatchObject({
    text: "Analysis",
    color: "#f16e76",
  });
  canvas.editText();
  canvas.finishText("Updated");
  expect(browserDrawings.load("drawings")[0]?.text).toBe("Updated");
  canvas.draw("simpleTag");
  finish(mock.items[1]!);
  canvas.finishText(null);
  expect(mock.items).toHaveLength(1);
  expect(browserDrawings.load("drawings")).toHaveLength(1);
});

it("switching tools and Escape remove only unfinished geometry", async () => {
  const { canvas } = await mountCanvas();
  canvas.draw("horizontalStraightLine");
  finish(mock.items[0]!);
  canvas.draw("segment");
  canvas.draw("priceChannelLine");
  expect(mock.items.map((item) => item.name)).toEqual([
    "horizontalStraightLine",
    "priceChannelLine",
  ]);
  document.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape" }));
  expect(mock.items.map((item) => item.name)).toEqual([
    "horizontalStraightLine",
  ]);
  expect(browserDrawings.load("drawings")).toHaveLength(1);
});

it("Delete removes the selection but leaves text editing and other panels alone", async () => {
  const { canvas } = await mountCanvas();
  canvas.draw("horizontalStraightLine");
  const item = mock.items[0]!;
  finish(item);
  item.onSelected?.({ overlay: item, chart: {} } as never);
  for (const tag of ["input", "textarea", "button", "div"]) {
    const element = document.createElement(tag);
    if (tag === "div") element.contentEditable = "true";
    document.body.append(element);
    element.dispatchEvent(
      new KeyboardEvent("keydown", {
        key: "Delete",
        bubbles: true,
        cancelable: true,
      }),
    );
    expect(mock.items).toHaveLength(1);
    element.remove();
  }
  document.dispatchEvent(
    new KeyboardEvent("keydown", {
      key: "Delete",
      cancelable: true,
    }),
  );
  expect(mock.items).toHaveLength(0);
  expect(browserDrawings.load("drawings")).toEqual([]);
});

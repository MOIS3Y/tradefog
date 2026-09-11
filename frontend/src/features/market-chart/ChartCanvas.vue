<script setup lang="ts">
/** Canvas boundary: only here do decimal candles become chart numbers. */
import { onBeforeUnmount, onMounted, ref, watch } from "vue";
import { useI18n } from "vue-i18n";
import type { Chart, KLineData, OverlayCreate, Overlay } from "klinecharts";
import {
  browserDrawings,
  defaultDrawingColor,
  drawingTools,
  isTextDrawing,
  type Drawing,
  type DrawingTool,
  type DrawingSelection,
} from "./drawings";
import type { MarketFeed } from "./feed";
import type { Candle, Timeframe } from "./types";
import { candlePrecision } from "./precision";
import { enableTextSelection } from "./text-overlays";

const props = defineProps<{
  feed: MarketFeed;
  timeframe: Timeframe;
  storageKey: string;
  chartType?: "candle_solid" | "ohlc" | "area";
  indicators?: string[];
}>();
const emit = defineEmits<{
  ready: [];
  failure: [];
  storageFailure: [];
  selected: [DrawingSelection | null];
  drawing: [DrawingTool | null];
  textRequest: [string];
  limit: [];
}>();
const root = ref<HTMLElement>();
const { locale } = useI18n({ useScope: "global" });
let chart: Chart | null = null;
let disposed = false;
let observer: ResizeObserver | undefined;
let disposeChart: (() => void) | undefined;
let push: ((bar: KLineData) => void) | undefined;
let selectedId: string | undefined;
let drawingId: string | undefined;
let pendingText: { id: string; fresh: boolean } | undefined;
let currentColor = defaultDrawingColor;
let retryHistory: (() => Promise<void>) | undefined;
let retryTimer: ReturnType<typeof setTimeout> | undefined;
let historyFailures = 0;
let restoring = false;
let initializing = false;
let generation = 0;
let drawingsRestored = false;
const activeIndicators = new Set<string>();

/** Diff built-in indicators without resetting the canvas or its history. */
function syncIndicators(): void {
  if (!chart) return;
  const wanted = props.indicators ?? [];
  for (const name of activeIndicators) {
    if (!wanted.includes(name)) {
      chart.removeIndicator({ name });
      activeIndicators.delete(name);
    }
  }
  for (const name of wanted) {
    if (activeIndicators.has(name)) continue;
    const overlay = ["MA", "EMA", "BOLL"].includes(name);
    chart.createIndicator(
      { name, ...(overlay ? { paneId: "candle_pane" } : {}) },
      true,
    );
    activeIndicators.add(name);
  }
}

/** Update display precision without resetting history or the viewport. */
function updatePrecision(bars: Candle[]): void {
  const symbol = chart?.getSymbol();
  if (!symbol) return;
  const next = candlePrecision(bars, symbol);
  if (
    next.pricePrecision === symbol.pricePrecision &&
    next.volumePrecision === symbol.volumePrecision
  )
    return;
  // KLineCharts 10 exposes the live symbol. setSymbol resets loaded data,
  // so update only its precision fields and redraw the existing chart.
  Object.assign(symbol, next);
  chart?.setStyles({});
}

/** Numeric conversion is limited to non-authoritative visualization. */
function visual(bar: Candle): KLineData {
  return {
    timestamp: bar.timestamp,
    open: Number(bar.open),
    high: Number(bar.high),
    low: Number(bar.low),
    close: Number(bar.close),
    volume: bar.volume === undefined ? undefined : Number(bar.volume),
    turnover: bar.turnover === undefined ? undefined : Number(bar.turnover),
  };
}

/** Persist completed drawings only; quota failures never block the chart. */
function save(): void {
  if (restoring || !chart) return;
  const overlays = chart
    .getOverlays()
    .filter(
      (item) =>
        item.currentStep === -1 &&
        !(pendingText?.fresh && pendingText.id === item.id),
    )
    .map((item) => ({
      name: item.name,
      points: item.points,
      color: item.styles?.line?.color ?? defaultDrawingColor,
      ...(isTextDrawing(item.name) ? { text: item.extendData } : {}),
    }));
  if (!browserDrawings.save(props.storageKey, overlays)) emit("storageFailure");
}

/** Reattach runtime callbacks rather than storing them in browser storage. */
function overlay(
  value: Drawing | { name: DrawingTool; color: string },
): OverlayCreate {
  return {
    name: value.name,
    needDefaultPointFigure: true,
    ...("points" in value ? { points: value.points } : {}),
    extendData: "text" in value ? value.text : undefined,
    styles: drawingStyles(value.color),
    onDrawEnd: ({ overlay: item }) => {
      if (restoring) return;
      drawingId = undefined;
      emit("drawing", null);
      if (isTextDrawing(item.name)) {
        pendingText = { id: item.id, fresh: true };
        emit("textRequest", "");
      } else save();
    },
    onPressedMoveEnd: save,
    onSelected: ({ overlay: item }) => {
      selectedId = item.id;
      emitSelection(item);
    },
    onDeselected: () => {
      selectedId = undefined;
      emit("selected", null);
    },
  };
}

/** Add only supported drawing tools from the containing toolbar. */
function draw(name: DrawingTool): void {
  cancelDrawing();
  if (!chart || !drawingTools.includes(name)) return;
  if (chart.getOverlays().length >= 100) {
    emit("limit");
    return;
  }
  selectedId = undefined;
  emit("selected", null);
  const id = chart.createOverlay(overlay({ name, color: currentColor }));
  drawingId = typeof id === "string" ? id : undefined;
  emit("drawing", name);
}

/** One foreground color; axis labels keep a contrasting background. */
function drawingStyles(color: string): OverlayCreate["styles"] {
  const backgroundColor = root.value
    ? getComputedStyle(root.value).getPropertyValue("--tf-panel").trim()
    : "#121922";
  return {
    line: { color },
    polygon: { color, borderColor: color },
    text: { color, backgroundColor, family: "IBM Plex Sans" },
  };
}

/** Expose editable metadata without leaking chart instances to the toolbar. */
function emitSelection(item: Overlay): void {
  currentColor = item.styles?.line?.color ?? defaultDrawingColor;
  emit("selected", {
    color: currentColor,
    ...(isTextDrawing(item.name)
      ? { text: String(item.extendData ?? "") }
      : {}),
  });
}

/** Cancel only an unfinished overlay, preserving completed drawings. */
function cancelDrawing(): void {
  if (drawingId) chart?.removeOverlay({ id: drawingId });
  drawingId = undefined;
  emit("drawing", null);
}

/** Apply color to the current selection and subsequent drawings. */
function setColor(color: string): void {
  if (!/^#[0-9a-f]{6}$/i.test(color)) return;
  currentColor = color;
  const id = drawingId ?? selectedId;
  if (id) chart?.overrideOverlay({ id, styles: drawingStyles(color) });
  save();
}

/** Request editing of a completed text-bearing overlay. */
function editText(): void {
  const item = chart?.getOverlays().find((item) => item.id === selectedId);
  if (!item || !isTextDrawing(item.name)) return;
  pendingText = { id: item.id, fresh: false };
  emit("textRequest", String(item.extendData ?? ""));
}

/** Commit text or discard only a newly placed, cancelled annotation. */
function finishText(text: string | null): void {
  if (!pendingText) return;
  const { id, fresh } = pendingText;
  if (
    text !== null &&
    (!text.trim() || text.length > 200 || /[\r\n]/.test(text))
  )
    return;
  pendingText = undefined;
  if (text === null && fresh) {
    chart?.removeOverlay({ id });
    selectedId = undefined;
    emit("selected", null);
  } else if (text !== null) {
    chart?.overrideOverlay({ id, extendData: text.trim() });
    const item = chart?.getOverlays().find((item) => item.id === id);
    if (item && selectedId === id) emitSelection(item);
  }
  save();
}

/** Handle drawing shortcuts without intercepting text or other panels. */
function drawingKeydown(event: KeyboardEvent): void {
  const target = event.target instanceof Element ? event.target : null;
  if (
    event.defaultPrevented ||
    target?.closest(
      'input, textarea, select, [contenteditable]:not([contenteditable="false"]), [role="textbox"], [role="menu"], [role="dialog"]',
    )
  )
    return;
  if (event.key === "Escape" && drawingId) {
    event.preventDefault();
    event.stopPropagation();
    cancelDrawing();
  }
  if (
    event.key === "Delete" &&
    selectedId &&
    !drawingId &&
    !pendingText &&
    !event.ctrlKey &&
    !event.metaKey &&
    !event.altKey &&
    !event.shiftKey &&
    (!target ||
      target === document.body ||
      root.value?.closest(".market-chart")?.contains(target))
  ) {
    event.preventDefault();
    event.stopPropagation();
    remove();
  }
}

/** Delete a selected annotation, leaving position values untouched. */
function remove(): void {
  if (selectedId) chart?.removeOverlay({ id: selectedId });
  selectedId = undefined;
  emit("selected", null);
  save();
}

/** Clear annotations after the containing UI asks for confirmation. */
function clear(): void {
  cancelDrawing();
  chart?.removeOverlay();
  selectedId = undefined;
  emit("selected", null);
  save();
}

/** Retry a failed history page without discarding the visible viewport. */
function retry(): void {
  clearTimeout(retryTimer);
  if (!chart) void initialize();
  else void retryHistory?.();
}

/** Initialize lazily; an import or canvas failure stays inside this panel. */
async function initialize(): Promise<void> {
  if (initializing || chart || disposed) return;
  initializing = true;
  try {
    const library = await import("klinecharts");
    if (disposed || !root.value) return;
    enableTextSelection(library);
    chart = library.init(root.value);
    if (!chart) throw new Error("Canvas initialization failed");
    const instance = chart;
    disposeChart = () => library.dispose(instance);
    const tokens = getComputedStyle(root.value);
    const color = (name: string): string =>
      tokens.getPropertyValue(`--tf-${name}`).trim();
    instance.setStyles({
      indicator: {
        bars: [
          {
            upColor: color("action"),
            downColor: color("danger"),
            noChangeColor: color("ink-soft"),
          },
        ],
        lines: ["type-equity", "type-fiat", "action", "danger"].map(
          (token) => ({ color: color(token) }),
        ),
        tooltip: {
          title: { family: "IBM Plex Mono", size: 11, color: color("ink") },
          legend: {
            family: "IBM Plex Mono",
            size: 10,
            color: color("ink-soft"),
          },
        },
      },
      grid: {
        horizontal: { color: color("line") },
        vertical: { color: color("line") },
      },
      candle: {
        type: props.chartType ?? "candle_solid",
        area: {
          lineColor: color("action"),
          backgroundColor: color("action-soft"),
          point: { animation: false },
        },
        bar: {
          upColor: color("action"),
          downColor: color("danger"),
          noChangeColor: color("ink-soft"),
          upBorderColor: color("action"),
          downBorderColor: color("danger"),
          upWickColor: color("action"),
          downWickColor: color("danger"),
        },
        tooltip: {
          showRule: "follow_cross",
          showType: "rect",
          title: { family: "IBM Plex Mono", size: 11, color: color("ink") },
          legend: {
            family: "IBM Plex Mono",
            size: 10,
            color: color("ink-soft"),
          },
          rect: { color: color("panel"), borderColor: color("line") },
        },
        priceMark: {
          high: { textFamily: "IBM Plex Mono", color: color("ink-soft") },
          low: { textFamily: "IBM Plex Mono", color: color("ink-soft") },
          last: {
            upColor: color("action"),
            downColor: color("danger"),
            text: { family: "IBM Plex Mono" },
          },
        },
      },
      xAxis: {
        tickText: { color: color("ink-soft"), family: "IBM Plex Mono" },
        axisLine: { color: color("line") },
      },
      yAxis: {
        tickText: { color: color("ink-soft"), family: "IBM Plex Mono" },
        axisLine: { color: color("line") },
      },
      overlay: { line: { color: color("type-fiat") } },
      crosshair: {
        horizontal: {
          text: {
            family: "IBM Plex Mono",
            backgroundColor: color("panel-raised"),
          },
        },
        vertical: {
          text: {
            family: "IBM Plex Mono",
            backgroundColor: color("panel-raised"),
          },
        },
      },
    });
    library.registerLocale("ru", {
      time: "Время",
      open: "Открытие",
      high: "Максимум",
      low: "Минимум",
      close: "Закрытие",
      volume: "Объём",
      second: "с",
      minute: "м",
      change: "Изменение",
      turnover: "Оборот",
      hour: "ч",
      day: "д",
      week: "н",
      month: "мес",
      year: "г",
    });
    instance.setLocale(locale.value === "ru" ? "ru" : "en-US");
    // Group thousands consistently without changing decimal precision.
    instance.setThousandsSeparator({ sign: "\u00a0" });
    instance.setTimezone(Intl.DateTimeFormat().resolvedOptions().timeZone);
    instance.setDataLoader({
      getBars({ type, timestamp, callback }) {
        if (type === "backward") {
          callback([], false);
          return;
        }
        let running = false;
        const context = generation;
        const load = async (): Promise<void> => {
          if (running || disposed || context !== generation) return;
          if (document.hidden) {
            retryTimer = setTimeout(() => void load(), 5000);
            return;
          }
          running = true;
          try {
            const { bars, hasMore } = await props.feed.history(
              type === "forward" ? (timestamp ?? undefined) : undefined,
            );
            if (disposed || context !== generation) return;
            updatePrecision(bars);
            callback(bars.map(visual), { forward: hasMore, backward: false });
            retryHistory = undefined;
            historyFailures = 0;
            if (type === "init") {
              if (!drawingsRestored) {
                restoring = true;
                instance.createOverlay(
                  browserDrawings.load(props.storageKey).map(overlay),
                );
                restoring = false;
                drawingsRestored = true;
              }
              emit("ready");
            }
          } catch (error) {
            if (disposed || context !== generation) return;
            retryHistory = load;
            // Hiding a panel is not a provider failure. Visibility resume
            // retries this loader without displaying an error or backoff.
            if (error instanceof DOMException && error.name === "AbortError")
              return;
            emit("failure");
            historyFailures = Math.min(historyFailures + 1, 4);
            retryTimer = setTimeout(
              () => void load(),
              Math.min(5000 * 2 ** historyFailures, 60_000),
            );
          } finally {
            running = false;
          }
        };
        retryHistory = load;
        void load();
      },
      subscribeBar({ callback }) {
        push = callback;
      },
      unsubscribeBar() {
        push = undefined;
      },
    });
    instance.setSymbol({
      ticker: props.feed.instrument.symbol,
      pricePrecision: 0,
      volumePrecision: 0,
    });
    instance.setPeriod({
      span: props.timeframe.span,
      type: props.timeframe.unit,
    });
    observer = new ResizeObserver(() => instance.resize());
    syncIndicators();
    observer.observe(root.value);
  } catch {
    emit("failure");
  } finally {
    initializing = false;
  }
}
onMounted(() => {
  document.addEventListener("keydown", drawingKeydown);
  void initialize();
});
watch(() => props.indicators, syncIndicators);
watch(
  () => props.timeframe,
  (period) => {
    generation++;
    clearTimeout(retryTimer);
    retryHistory = undefined;
    historyFailures = 0;
    selectedId = undefined;
    cancelDrawing();
    emit("selected", null);
    const symbol = chart?.getSymbol();
    if (symbol)
      Object.assign(symbol, { pricePrecision: 0, volumePrecision: 0 });
    chart?.setPeriod({ span: period.span, type: period.unit });
  },
);
watch(locale, (value) => chart?.setLocale(value === "ru" ? "ru" : "en-US"));
watch(
  () => props.chartType,
  (type) => {
    chart?.setStyles({ candle: { type: type ?? "candle_solid" } });
  },
);

onBeforeUnmount(() => {
  document.removeEventListener("keydown", drawingKeydown);
  disposed = true;
  clearTimeout(retryTimer);
  observer?.disconnect();
  disposeChart?.();
});

defineExpose({
  draw,
  cancelDrawing,
  setColor,
  editText,
  finishText,
  remove,
  clear,
  retry,
  update: (bars: Candle[]): void => {
    updatePrecision(bars);
    for (const bar of bars) push?.(visual(bar));
  },
  latest: (): void => chart?.scrollToRealTime(),
  snapshot: (): string | undefined =>
    chart?.getConvertPictureUrl(
      true,
      "png",
      getComputedStyle(root.value!).getPropertyValue("--tf-canvas").trim(),
    ),
});
</script>

<template><div ref="root" class="market-chart__canvas" /></template>

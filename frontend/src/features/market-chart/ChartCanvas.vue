<script setup lang="ts">
/** Canvas boundary: only here do decimal candles become chart numbers. */
import { onBeforeUnmount, onMounted, ref, watch } from "vue";
import { useI18n } from "vue-i18n";
import type { Chart, KLineData, OverlayCreate } from "klinecharts";
import { browserDrawings, type Drawing } from "./drawings";
import type { MarketFeed } from "./feed";
import type { Candle, Timeframe } from "./types";
import { candlePrecision } from "./precision";

const props = defineProps<{
  feed: MarketFeed;
  timeframe: Timeframe;
  storageKey: string;
  chartType?: "candle_solid" | "ohlc" | "area";
}>();
const emit = defineEmits<{
  ready: [];
  failure: [];
  storageFailure: [];
  selected: [boolean];
}>();
const root = ref<HTMLElement>();
const { locale } = useI18n({ useScope: "global" });
let chart: Chart | null = null;
let disposed = false;
let observer: ResizeObserver | undefined;
let disposeChart: (() => void) | undefined;
let push: ((bar: KLineData) => void) | undefined;
let selectedId: string | undefined;
let retryHistory: (() => Promise<void>) | undefined;
let retryTimer: ReturnType<typeof setTimeout> | undefined;
let historyFailures = 0;
let restoring = false;
let initializing = false;
let generation = 0;
let drawingsRestored = false;

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
    .filter((overlay) => overlay.currentStep === -1);
  if (!browserDrawings.save(props.storageKey, overlays)) emit("storageFailure");
}

/** Reattach runtime callbacks rather than storing them in browser storage. */
function overlay(value: Drawing | { name: string }): OverlayCreate {
  return {
    ...value,
    onDrawEnd: save,
    onPressedMoveEnd: save,
    onSelected: ({ overlay: item }) => {
      selectedId = item.id;
      emit("selected", true);
    },
    onDeselected: () => {
      selectedId = undefined;
      emit("selected", false);
    },
  };
}

/** Add only supported drawing tools from the containing toolbar. */
function draw(name: string): void {
  if ((chart?.getOverlays().length ?? 0) < 100)
    chart?.createOverlay(overlay({ name }));
}

/** Delete a selected annotation, leaving position values untouched. */
function remove(): void {
  if (selectedId) chart?.removeOverlay({ id: selectedId });
  selectedId = undefined;
  emit("selected", false);
  save();
}

/** Clear annotations after the containing UI asks for confirmation. */
function clear(): void {
  chart?.removeOverlay();
  selectedId = undefined;
  emit("selected", false);
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
    chart = library.init(root.value);
    if (!chart) throw new Error("Canvas initialization failed");
    const instance = chart;
    disposeChart = () => library.dispose(instance);
    const tokens = getComputedStyle(root.value);
    const color = (name: string): string =>
      tokens.getPropertyValue(`--tf-${name}`).trim();
    instance.setStyles({
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
    observer.observe(root.value);
  } catch {
    emit("failure");
  } finally {
    initializing = false;
  }
}
onMounted(initialize);
watch(
  () => props.timeframe,
  (period) => {
    generation++;
    clearTimeout(retryTimer);
    retryHistory = undefined;
    historyFailures = 0;
    selectedId = undefined;
    emit("selected", false);
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
  disposed = true;
  clearTimeout(retryTimer);
  observer?.disconnect();
  disposeChart?.();
});

defineExpose({
  draw,
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

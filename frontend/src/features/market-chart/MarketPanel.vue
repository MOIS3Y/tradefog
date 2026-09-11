<script setup lang="ts">
/** Optional market UI with no authority over trade planning or lifecycle. */
import {
  ArrowRight,
  ChartCandlestick,
  ChartNoAxesColumn,
  ChartLine,
  Camera,
  ExternalLink,
  Maximize2,
  Minimize2,
} from "@lucide/vue";
import {
  computed,
  onBeforeUnmount,
  onMounted,
  reactive,
  ref,
  watch,
} from "vue";
import { useI18n } from "vue-i18n";
import ChartCanvas from "./ChartCanvas.vue";
import OrderBookPanel from "./OrderBookPanel.vue";
import DrawingToolbar from "./DrawingToolbar.vue";
import type { DrawingSelection, DrawingTool } from "./drawings";
import { MarketFeed } from "./feed";
import type { MarketAdapter, MarketInstrument } from "./types";

const props = defineProps<{
  adapter: MarketAdapter;
  instrument: MarketInstrument;
  storageKey: string;
  saveSnapshot: (file: File) => Promise<void>;
}>();
const { t: translate, locale } = useI18n({ useScope: "global" });
/** Resolve feature copy through the shared journal namespace. */
const t = (key: string, values: Record<string, string> = {}) =>
  translate("marketChart." + key, values);
const root = ref<HTMLElement>();
const chartRoot = ref<HTMLElement>();
const fullscreen = ref(false);
const fullscreenFailed = ref(false);
const chartType = ref<"candle_solid" | "ohlc" | "area">("candle_solid");
const indicators = ref<string[]>(["VOL"]);
const indicatorNames = ["VOL", "MA", "EMA", "BOLL", "RSI", "MACD"];
/** Toggle built-ins without reloading market history. */
function toggleIndicator(name: string): void {
  indicators.value = indicators.value.includes(name)
    ? indicators.value.filter((item) => item !== name)
    : [...indicators.value, name];
}
const chartTypes = computed(() => [
  { value: "candle_solid" as const, label: t("candles") },
  { value: "ohlc" as const, label: t("bars") },
  { value: "area" as const, label: t("line") },
]);
const canvas = ref<InstanceType<typeof ChartCanvas>>();
const timeframe = ref(
  props.adapter.timeframes.find((item) => item.value === "15m")?.value ??
    props.adapter.timeframes[0]?.value ??
    "",
);
const period = computed(() =>
  props.adapter.timeframes.find((item) => item.value === timeframe.value)!,
);
const bookPanel = ref<InstanceType<typeof OrderBookPanel>>();
const expanded = ref(true);
const ready = ref(false);
const selected = ref<DrawingSelection | null>(null);
const activeDrawing = ref<DrawingTool | null>(null);
const textRequest = ref<{ text: string } | null>(null);
const drawingLimit = ref(false);

/** Complete or cancel text editing at the canvas boundary. */
function finishText(value: string | null): void {
  canvas.value?.finishText(value);
  textRequest.value = null;
}
const clearConfirm = ref(false);
const storageFailed = ref(false);
const uploading = ref(false);
const snapshotStatus = ref<"saved" | "snapshotError" | null>(null);
const failures = reactive({ chart: false });
const refreshing = ref(true);
const lastReceived = ref("");
let updatedChart = 0;
let visible = true;
let observer: IntersectionObserver | undefined;
const feed = new MarketFeed(props.adapter, props.instrument, timeframe.value, {
  candles: (bars) => canvas.value?.update(bars),
  book: (value) => bookPanel.value?.update(value),
  price: (value) => bookPanel.value?.updatePrice(value),
  refreshing: () => {
    refreshing.value = true;
  },
  status: (panel, failed) => {
    if (panel === "book") {
      bookPanel.value?.status(failed);
      return;
    }
    failures.chart = failed;
    refreshing.value = false;
    if (!failed) updatedChart = Date.now();
    lastReceived.value =
      failed && updatedChart
        ? new Intl.DateTimeFormat(locale.value, {
            hour: "2-digit",
            minute: "2-digit",
            second: "2-digit",
            hourCycle: "h23",
          }).format(updatedChart)
        : "";
  },
});

/** Suspend network activity when the browser or entire market block is hidden. */
function visibility(): void {
  if (document.hidden || (!visible && !fullscreen.value)) feed.pause();
  else {
    feed.resume();
    canvas.value?.retry();
  }
}

/** Keep the same canvas mounted; the browser handles Escape and focus. */
async function toggleFullscreen(): Promise<void> {
  fullscreenFailed.value = false;
  try {
    if (document.fullscreenElement === chartRoot.value) {
      await document.exitFullscreen();
    } else {
      await chartRoot.value?.requestFullscreen();
    }
  } catch {
    fullscreenFailed.value = true;
  }
}

/** Track browser-initiated exits and stop polling the hidden order book. */
function fullscreenChanged(): void {
  fullscreen.value =
    !!chartRoot.value && document.fullscreenElement === chartRoot.value;
  feed.bookVisible = expanded.value && !fullscreen.value;
  visibility();
}

/** Export and upload through a callback supplied by the journal boundary. */
async function snapshot(): Promise<void> {
  if (uploading.value) return;
  uploading.value = true;
  snapshotStatus.value = null;
  try {
    const url = canvas.value?.snapshot();
    if (!url) throw new Error("Chart not ready");
    const blob = await (await fetch(url)).blob();
    await props.saveSnapshot(
      new File(
        [blob],
        `${props.instrument.symbol}-${timeframe.value}-${Date.now()}.png`,
        { type: "image/png" },
      ),
    );
    snapshotStatus.value = "saved";
  } catch {
    snapshotStatus.value = "snapshotError";
  } finally {
    uploading.value = false;
  }
}

watch(timeframe, (value) => {
  ready.value = false;
  selected.value = null;
  failures.chart = false;
  updatedChart = 0;
  lastReceived.value = "";
  feed.changeTimeframe(value);
});
watch(expanded, (value) => {
  feed.bookVisible = value && !fullscreen.value;
});
onMounted(() => {
  document.addEventListener("fullscreenchange", fullscreenChanged);
  document.addEventListener("visibilitychange", visibility);
  if (typeof IntersectionObserver !== "undefined" && root.value) {
    observer = new IntersectionObserver(([entry]) => {
      visible = entry?.isIntersecting ?? false;
      visibility();
    });
    observer.observe(root.value);
  }
  visibility();
});
onBeforeUnmount(() => {
  document.removeEventListener("fullscreenchange", fullscreenChanged);
  feed.pause();
  observer?.disconnect();
  document.removeEventListener("visibilitychange", visibility);
});
</script>

<template>
  <div
    ref="root"
    class="market-panel"
    :class="{ 'market-panel--single': !adapter.candles || !adapter.book }"
  >
    <section
      v-if="adapter.candles"
      ref="chartRoot"
      class="market-chart"
      :style="{
        '--indicator-extra': `${Math.max(0, indicators.filter((name) => ['VOL', 'RSI', 'MACD'].includes(name)).length - 1) * 100}px`,
      }"
      :aria-label="t('chart')"
    >
      <header class="market-panel__header">
        <strong>{{ instrument.symbol }}</strong>
        <div
          class="market-chart__types"
          role="group"
          :aria-label="t('chartType')"
        >
          <button
            v-for="(item, index) in chartTypes"
            :key="item.value"
            type="button"
            class="icon-action"
            :aria-label="item.label"
            :title="item.label"
            :aria-pressed="chartType === item.value"
            @click="chartType = item.value"
          >
            <component
              :is="[ChartCandlestick, ChartNoAxesColumn, ChartLine][index]"
              :size="16"
            />
          </button>
        </div>
        <button
          type="button"
          class="icon-action"
          :aria-label="t(fullscreen ? 'exitFullscreen' : 'fullscreen')"
          :title="t(fullscreen ? 'exitFullscreen' : 'fullscreen')"
          :aria-pressed="fullscreen"
          @click="toggleFullscreen"
        >
          <Minimize2 v-if="fullscreen" :size="15" />
          <Maximize2 v-else :size="15" />
        </button>
        <a
          :href="adapter.link(instrument)"
          target="_blank"
          rel="noopener noreferrer"
          :title="t('exchange', { name: adapter.name })"
          :aria-label="t('exchange', { name: adapter.name })"
          class="icon-action"
          ><ExternalLink :size="15"
        /></a>
      </header>
      <div
        class="market-chart__periods"
        role="group"
        :aria-label="t('timeframe')"
      >
        <button
          v-for="item in adapter.timeframes"
          :key="item.value"
          type="button"
          :aria-pressed="timeframe === item.value"
          @click="timeframe = item.value"
        >
          {{ item.label }}
        </button>
      </div>
      <details class="market-chart__indicators">
        <summary>{{ t("indicators") }}</summary>
        <div role="group" :aria-label="t('indicators')">
          <button
            v-for="name in indicatorNames"
            :key="name"
            type="button"
            :aria-pressed="indicators.includes(name)"
            @click="toggleIndicator(name)"
          >
            {{ name === "VOL" ? t("volume") : name }}
          </button>
        </div>
      </details>
      <div
        class="market-chart__toolbar"
        role="toolbar"
        :aria-label="t('chart')"
      >
        <button
          type="button"
          class="market-text-button"
          :disabled="!ready"
          @click="clearConfirm = !clearConfirm"
        >
          {{ t("clear") }}
        </button>
        <button
          type="button"
          class="icon-action"
          :disabled="!ready"
          :title="t('latest')"
          :aria-label="t('latest')"
          @click="canvas?.latest()"
        >
          <ArrowRight :size="16" />
        </button>
        <button
          type="button"
          class="icon-action"
          :disabled="!ready || uploading"
          :title="t('snapshot')"
          :aria-label="t('snapshot')"
          @click="snapshot"
        >
          <Camera :size="16" />
        </button>
      </div>
      <div v-if="clearConfirm" class="market-chart__confirmation">
        <span>{{ t("confirm") }}</span
        ><button
          class="market-text-button"
          @click="
            canvas?.clear();
            clearConfirm = false;
          "
        >
          {{ t("clear") }}</button
        ><button class="market-text-button" @click="clearConfirm = false">
          {{ t("cancel") }}
        </button>
      </div>
      <div class="market-chart__drawing-area">
        <DrawingToolbar
          :ready="ready"
          :selected="selected"
          :active="activeDrawing"
          :text-request="textRequest"
          @draw="canvas?.draw($event)"
          @cancel="canvas?.cancelDrawing()"
          @color="canvas?.setColor($event)"
          @remove="canvas?.remove()"
          @edit-text="canvas?.editText()"
          @finish-text="finishText"
        />
        <div class="market-chart__plot">
          <ChartCanvas
            ref="canvas"
            :style="{ visibility: ready ? 'visible' : 'hidden' }"
            :feed="feed"
            :timeframe="period"
            :chart-type="chartType"
            :indicators="indicators"
            :storage-key="storageKey"
            @ready="ready = true"
            @failure="failures.chart = true"
            @storage-failure="storageFailed = true"
            @selected="selected = $event"
            @drawing="activeDrawing = $event"
            @text-request="textRequest = { text: $event }"
            @limit="drawingLimit = true"
          />
          <p v-if="!ready" class="market-chart__loading" role="status">
            {{ t(failures.chart ? "failed" : "loading")
            }}<button
              v-if="failures.chart"
              class="market-text-button"
              @click="canvas?.retry()"
            >
              {{ t("retry") }}
            </button>
          </p>
        </div>
      </div>
      <p v-if="drawingLimit" class="market-panel__warning" role="status">
        {{ t("drawingLimit") }}
        <button class="market-text-button" @click="drawingLimit = false">
          {{ t("dismiss") }}
        </button>
      </p>
      <footer class="market-panel__status">
        <span>{{ t(storageFailed ? "storage" : "local") }}</span
        ><span v-if="ready && refreshing">{{ t("refreshing") }}</span>
      </footer>
      <p
        v-if="failures.chart && ready"
        class="market-panel__warning"
        role="status"
      >
        {{ t("stale") }}
        <span v-if="lastReceived">{{
          t("lastUpdated", { time: lastReceived })
        }}</span>
      </p>
      <p v-if="fullscreenFailed" class="market-panel__warning" role="status">
        {{ t("fullscreenFailed") }}
      </p>
      <p v-if="snapshotStatus" class="market-panel__warning" role="status">
        {{ t(snapshotStatus) }}
      </p>
    </section>
    <OrderBookPanel
      v-if="adapter.book"
      ref="bookPanel"
      :has-chart="!!adapter.candles"
      :exchange-name="adapter.name"
      :exchange-url="adapter.link(instrument)"
      :base="instrument.base"
      :quote="instrument.quote"
      @expanded="expanded = $event"
    />
  </div>
</template>

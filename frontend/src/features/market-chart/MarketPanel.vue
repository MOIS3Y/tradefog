<script setup lang="ts">
/** Optional market UI with no authority over trade planning or lifecycle. */
import {
  ArrowRight,
  Camera,
  ChevronDown,
  ExternalLink,
  Maximize2,
  Minimize2,
  Minus,
  MoveUpRight,
  Trash2,
} from "@lucide/vue";
import Decimal from "decimal.js";
import {
  computed,
  nextTick,
  onBeforeUnmount,
  onMounted,
  reactive,
  ref,
  watch,
} from "vue";
import { useI18n } from "vue-i18n";
import AppSelect from "@/components/AppSelect.vue";
import { formatDecimal } from "@/utils/decimal";
import ChartCanvas from "./ChartCanvas.vue";
import { drawingTools } from "./drawings";
import { MarketFeed } from "./feed";
import { messages } from "./messages";
import type { MarketAdapter, MarketInstrument, OrderBook } from "./types";

const props = defineProps<{
  adapter: MarketAdapter;
  instrument: MarketInstrument;
  storageKey: string;
  saveSnapshot: (file: File) => Promise<void>;
}>();
const { t, locale } = useI18n({ messages, useScope: "local" });
const root = ref<HTMLElement>();
const chartRoot = ref<HTMLElement>();
const fullscreen = ref(false);
const fullscreenFailed = ref(false);
const chartType = ref<"candle_solid" | "ohlc" | "area">("candle_solid");
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
const book = ref<OrderBook>();
const bookSide = ref<"both" | "asks" | "bids">("both");
const bookSides = computed(() =>
  bookSide.value === "both" ? (["asks", "bids"] as const) : [bookSide.value],
);
const depthMaximum = computed(() =>
  Decimal.max(
    book.value?.bids.at(-1)?.total ?? "0",
    book.value?.asks.at(-1)?.total ?? "0",
  ),
);
function depthWidth(total: string): string {
  return depthMaximum.value.isZero()
    ? "0%"
    : `${new Decimal(total).div(depthMaximum.value).mul(100).toNumber()}%`;
}
const depth = ref<HTMLElement>();
const expanded = ref(true);
const ready = ref(false);
const selected = ref(false);
const clearConfirm = ref(false);
const storageFailed = ref(false);
const uploading = ref(false);
const snapshotStatus = ref<"saved" | "snapshotError" | null>(null);
const failures = reactive({ chart: false, book: false });
const updated = reactive({ chart: 0, book: 0 });
let visible = true;
let observer: IntersectionObserver | undefined;
const feed = new MarketFeed(props.adapter, props.instrument, timeframe.value, {
  candles: (bars) => canvas.value?.update(bars),
  book: (value) => {
    book.value = value;
  },
  status: (panel, failed) => {
    failures[panel] = failed;
    if (!failed) updated[panel] = Date.now();
  },
});
const spread = computed(() =>
  book.value?.asks[0] && book.value.bids[0]
    ? new Decimal(book.value.asks[0].price)
        .minus(book.value.bids[0].price)
        .toFixed()
    : "",
);

/** Display separate successful receipt times; REST snapshots are not atomic. */
function time(value: number): string {
  return value
    ? new Intl.DateTimeFormat(locale.value, {
        hour: "2-digit",
        minute: "2-digit",
        second: "2-digit",
        hourCycle: "h23",
      }).format(value)
    : "";
}

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
  selected.value = false;
  feed.changeTimeframe(value);
});
watch(expanded, (value) => {
  feed.bookVisible = value && !fullscreen.value;
});
watch(
  () => !!book.value && expanded.value,
  async (value) => {
    if (!value) return;
    await nextTick();
    if (depth.value)
      depth.value.scrollTop = Math.max(
        0,
        (depth.value.scrollHeight - depth.value.clientHeight) / 2,
      );
  },
);
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
      :aria-label="t('chart')"
    >
      <header class="market-panel__header">
        <strong>{{ instrument.symbol }}</strong>
        <AppSelect
          v-model="timeframe"
          :options="adapter.timeframes"
          :label="t('timeframe')"
          :portal-to="chartRoot"
        />
        <div class="market-chart__type">
          <AppSelect
            v-model="chartType"
            :options="chartTypes"
            :label="t('chartType')"
            :portal-to="chartRoot"
          />
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
        class="market-chart__toolbar"
        role="toolbar"
        :aria-label="t('chart')"
      >
        <button
          v-for="tool in drawingTools"
          :key="tool"
          type="button"
          class="icon-action"
          :disabled="!ready"
          :title="t(tool)"
          :aria-label="t(tool)"
          @click="canvas?.draw(tool)"
        >
          <Minus v-if="tool.startsWith('horizontal')" :size="16" /><MoveUpRight
            v-else
            :size="16"
          /><small v-if="tool.endsWith('RayLine') || tool === 'rayLine'"
            >→</small
          >
        </button>
        <button
          type="button"
          class="icon-action"
          :disabled="!selected"
          :title="t('remove')"
          :aria-label="t('remove')"
          @click="canvas?.remove()"
        >
          <Trash2 :size="15" />
        </button>
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
      <div class="market-chart__plot">
        <ChartCanvas
          ref="canvas"
          :key="timeframe"
          :feed="feed"
          :timeframe="period"
          :chart-type="chartType"
          :storage-key="storageKey"
          @ready="ready = true"
          @failure="failures.chart = true"
          @storage-failure="storageFailed = true"
          @selected="selected = $event"
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
      <footer class="market-panel__status">
        <span>{{ t(storageFailed ? "storage" : "local") }}</span
        ><time v-if="updated.chart">{{ time(updated.chart) }}</time>
      </footer>
      <p
        v-if="failures.chart && ready"
        class="market-panel__warning"
        role="status"
      >
        {{ t("stale") }}
      </p>
      <p v-if="fullscreenFailed" class="market-panel__warning" role="status">
        {{ t("fullscreenFailed") }}
      </p>
      <p v-if="snapshotStatus" class="market-panel__warning" role="status">
        {{ t(snapshotStatus) }}
      </p>
    </section>
    <section v-if="adapter.book" class="market-book" :aria-label="t('book')">
      <a
        v-if="!adapter.candles"
        class="market-text-button"
        :href="adapter.link(instrument)"
        target="_blank"
        rel="noopener noreferrer"
        >{{ t("exchange", { name: adapter.name }) }}</a
      >
      <button
        type="button"
        class="market-book__toggle"
        :aria-expanded="expanded"
        @click="expanded = !expanded"
      >
        <strong>{{ t("book") }}</strong
        ><ChevronDown :size="15" />
      </button>
      <template v-if="expanded">
        <p class="market-book__caption">{{ t("current") }}</p>
        <div class="market-book__modes" role="group" :aria-label="t('sides')">
          <button
            v-for="side in ['both', 'bids', 'asks'] as const"
            :key="side"
            type="button"
            :aria-pressed="bookSide === side"
            :class="{ active: bookSide === side }"
            @click="bookSide = side"
          >
            {{ t(side) }}
          </button>
        </div>
        <p v-if="!book" class="market-panel__status" role="status">
          {{ t(failures.book ? "stale" : "loading") }}
        </p>
        <template v-if="book">
          <div class="market-book__labels">
            <span>{{ t("price") }}</span
            ><span>{{ t("size") }}</span
            ><span>{{ t("total") }}</span>
          </div>
          <div ref="depth" class="market-book__depth">
            <div
              v-for="side in bookSides"
              :key="side"
              :class="`market-book__${side}`"
            >
              <div v-if="side === 'bids'" class="market-book__spread">
                <span>{{ t("spread") }}</span
                ><strong>{{ formatDecimal(spread) }}</strong>
              </div>
              <div
                v-for="level in side === 'asks'
                  ? [...book.asks].reverse()
                  : book.bids"
                :key="level.price"
                class="market-book__row"
                :style="{ '--depth-width': depthWidth(level.total) }"
              >
                <span :title="formatDecimal(level.price)">{{
                  formatDecimal(level.price)
                }}</span
                ><span :title="formatDecimal(level.size)">{{
                  formatDecimal(level.size)
                }}</span
                ><span :title="formatDecimal(level.total)">{{
                  formatDecimal(level.total)
                }}</span>
              </div>
            </div>
          </div>
          <footer class="market-panel__status">
            <time>{{ time(updated.book) }}</time>
          </footer>
        </template>
        <p
          v-if="failures.book && book"
          class="market-panel__warning"
          role="status"
        >
          {{ t("stale") }}
        </p>
      </template>
    </section>
  </div>
</template>

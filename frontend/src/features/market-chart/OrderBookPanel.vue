<script setup lang="ts">
/** Snapshot-only depth rendering, isolated from chart activity. */
import { ArrowUp, ArrowDown, ArrowLeftRight, ChevronDown } from "@lucide/vue";
import Decimal from "decimal.js";
import { computed, nextTick, ref, shallowRef, watch } from "vue";
import { useI18n } from "vue-i18n";
import { formatDecimal } from "@/utils/decimal";
import AppSelect from "@/components/AppSelect.vue";
import { groupLevels, groupingSteps } from "./grouping";
import { formatBookAmount } from "./book-format";
import type { OrderBook } from "./types";

defineProps<{
  hasChart: boolean;
  exchangeName: string;
  exchangeUrl: string;
  base: string;
  quote: string;
}>();
const emit = defineEmits<{ expanded: [boolean] }>();
const { t: translate, locale } = useI18n({ useScope: "global" });
/** Resolve feature copy through the shared journal namespace. */
const t = (key: string, values: Record<string, string> = {}) =>
  translate("marketChart." + key, values);
const book = shallowRef<OrderBook>();
const step = ref("0");
const unit = ref<"base" | "quote">("base");
const steps = ref<string[]>([]);
const options = computed(() => [
  ...steps.value.map((value) => ({ value, label: formatDecimal(value) })),
]);
const lastPrice = ref("");
const displayedPrice = computed(() => formatDecimal(lastPrice.value));
const direction = ref(0);

/** Price direction is relative to the previous poll, not the aggressor side. */
function updatePrice(value: string): void {
  if (lastPrice.value === value) return;
  direction.value = lastPrice.value
    ? new Decimal(value).cmp(lastPrice.value)
    : 0;
  lastPrice.value = value;
}
const failed = ref(false);
const lastReceived = ref("");
const expanded = ref(true);
const bookSide = ref<"both" | "asks" | "bids">("both");
const bookSides = computed(() =>
  bookSide.value === "both" ? (["asks", "bids"] as const) : [bookSide.value],
);
const depth = ref<HTMLElement>();
let updated = 0;

/** Prepare labels only when depth, grouping, or volume units change. */
const rows = computed(() => {
  const grouped = {
    bids: groupLevels(book.value?.bids ?? [], step.value, "bids", unit.value),
    asks: groupLevels(book.value?.asks ?? [], step.value, "asks", unit.value),
  };
  const maximum = Decimal.max(
    grouped.bids.at(-1)?.total ?? "0",
    grouped.asks.at(-1)?.total ?? "0",
  );
  const pricePlaces = new Decimal(step.value).decimalPlaces();
  const prepare = (side: "asks" | "bids") =>
    grouped[side].map((level) => ({
      exact: level,
      price: new Decimal(level.price).toFixed(pricePlaces),
      size: formatBookAmount(level.size),
      total: formatBookAmount(level.total),
      width: maximum.isZero()
        ? "0%"
        : `${new Decimal(level.total).div(maximum).mul(100).toNumber()}%`,
    }));
  return { asks: prepare("asks").reverse(), bids: prepare("bids") };
});
const spread = computed(() =>
  book.value?.asks[0] && book.value.bids[0]
    ? new Decimal(book.value.asks[0].price)
        .minus(book.value.bids[0].price)
        .toFixed()
    : "",
);
const displayedSpread = computed(() => formatDecimal(spread.value));

/** Receipt time is diagnostic only and does not trigger per-second renders. */
function status(value: boolean): void {
  if (!value) updated = Date.now();
  failed.value = value;
  lastReceived.value =
    value && updated
      ? new Intl.DateTimeFormat(locale.value, {
          hour: "2-digit",
          minute: "2-digit",
          second: "2-digit",
          hourCycle: "h23",
        }).format(updated)
      : "";
}

/** Ignore snapshot timestamp changes when the visible levels are identical. */
function update(value: OrderBook): void {
  const current = book.value;
  const same =
    current &&
    (["asks", "bids"] as const).every(
      (side) =>
        current[side].length === value[side].length &&
        current[side].every((level, i) => {
          const next = value[side][i]!;
          return (
            level.price === next.price &&
            level.size === next.size &&
            level.total === next.total
          );
        }),
    );
  if (!same) book.value = value;
  if (!steps.value.length && (value.bids.length || value.asks.length)) {
    steps.value = groupingSteps([...value.bids, ...value.asks]);
    step.value = steps.value[0]!;
  }
}
watch(expanded, (value) => emit("expanded", value));
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
defineExpose({ update, status, updatePrice });
</script>

<template>
  <section class="market-book" :aria-label="t('book')">
    <a
      v-if="!hasChart"
      class="market-text-button"
      :href="exchangeUrl"
      target="_blank"
      rel="noopener noreferrer"
      >{{ t("exchange", { name: exchangeName }) }}</a
    >
    <div class="market-book__header">
      <strong>{{ t("book") }}</strong>
      <button
        v-if="expanded"
        type="button"
        class="market-book__unit"
        :aria-label="t('volumeUnit', { asset: unit === 'base' ? base : quote })"
        :title="
          t('switchVolumeUnit', { asset: unit === 'base' ? quote : base })
        "
        @click="unit = unit === 'base' ? 'quote' : 'base'"
      >
        <span>{{ unit === "base" ? base : quote }}</span>
        <ArrowLeftRight :size="12" aria-hidden="true" />
      </button>
      <button
        type="button"
        class="market-book__toggle"
        :aria-label="t('book')"
        :aria-expanded="expanded"
        @click="expanded = !expanded"
      >
        <ChevronDown :size="15" />
      </button>
    </div>
    <template v-if="expanded">
      <p class="market-book__caption">{{ t("current") }}</p>
      <div class="market-book__controls">
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
        <div v-if="steps.length" class="market-book__grouping">
          <AppSelect v-model="step" :options="options" :label="t('grouping')" />
        </div>
      </div>
      <p v-if="!book" class="market-panel__status" role="status">
        {{ t(failed ? "stale" : "loading") }}
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
            <div
              v-if="side === 'bids' || bookSide === 'asks'"
              class="market-book__spread"
            >
              <strong
                v-if="lastPrice"
                class="market-book__last"
                :class="{ 'is-up': direction > 0, 'is-down': direction < 0 }"
                :title="t('lastPrice')"
                :aria-label="t('lastPrice')"
              >
                <ArrowUp v-if="direction > 0" :size="16" />
                <ArrowDown v-else-if="direction < 0" :size="16" />
                {{ displayedPrice }}
              </strong>
              <span v-else>{{ t("spread") }} {{ displayedSpread }}</span>
            </div>
            <div
              v-for="level in rows[side]"
              :key="level.price"
              class="market-book__row"
              :style="{ '--depth-width': level.width }"
            >
              <span :title="level.exact.price">{{ level.price }}</span
              ><span :title="level.exact.size">{{ level.size }}</span
              ><span :title="level.exact.total">{{ level.total }}</span>
            </div>
          </div>
        </div>
      </template>
      <p v-if="steps.length && step !== steps[0]" class="market-panel__status">
        {{ t("depthNote") }}
      </p>
      <p v-if="failed && book" class="market-panel__warning" role="status">
        {{ t("stale") }}
        <span v-if="lastReceived">{{
          t("lastUpdated", { time: lastReceived })
        }}</span>
      </p>
    </template>
  </section>
</template>

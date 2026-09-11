<script setup lang="ts">
/** Snapshot-only depth rendering, isolated from chart activity. */
import { ChevronDown } from "@lucide/vue";
import Decimal from "decimal.js";
import { computed, nextTick, ref, shallowRef, watch } from "vue";
import { useI18n } from "vue-i18n";
import { formatDecimal } from "@/utils/decimal";
import { messages } from "./messages";
import type { OrderBook } from "./types";

defineProps<{ hasChart: boolean; exchangeName: string; exchangeUrl: string }>();
const emit = defineEmits<{ expanded: [boolean] }>();
const { t, locale } = useI18n({ messages, useScope: "local" });
const book = shallowRef<OrderBook>();
const failed = ref(false);
const lastReceived = ref("");
const expanded = ref(true);
const bookSide = ref<"both" | "asks" | "bids">("both");
const bookSides = computed(() =>
  bookSide.value === "both" ? (["asks", "bids"] as const) : [bookSide.value],
);
const depth = ref<HTMLElement>();
let updated = 0;

/** Prepare exact display values only when snapshot levels change. */
const rows = computed(() => {
  const maximum = Decimal.max(
    book.value?.bids.at(-1)?.total ?? "0",
    book.value?.asks.at(-1)?.total ?? "0",
  );
  const prepare = (side: "asks" | "bids") =>
    (book.value?.[side] ?? []).map((level) => ({
      price: formatDecimal(level.price),
      size: formatDecimal(level.size),
      total: formatDecimal(level.total),
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
defineExpose({ update, status });
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
            <div v-if="side === 'bids'" class="market-book__spread">
              <span>{{ t("spread") }}</span
              ><strong>{{ formatDecimal(spread) }}</strong>
            </div>
            <div
              v-for="level in rows[side]"
              :key="level.price"
              class="market-book__row"
              :style="{ '--depth-width': level.width }"
            >
              <span :title="level.price">{{ level.price }}</span
              ><span :title="level.size">{{ level.size }}</span
              ><span :title="level.total">{{ level.total }}</span>
            </div>
          </div>
        </div>
      </template>
      <p v-if="failed && book" class="market-panel__warning" role="status">
        {{ t("stale") }}
        <span v-if="lastReceived">{{
          t("lastUpdated", { time: lastReceived })
        }}</span>
      </p>
    </template>
  </section>
</template>

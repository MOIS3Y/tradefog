<script setup lang="ts">
import Decimal from "decimal.js";
import { computed } from "vue";
import { useI18n } from "vue-i18n";

import type { Direction } from "@/features/trades/api";
import { calculatePositionScale } from "@/features/trades/positionScale";
import { formatDecimal } from "@/utils/decimal";

const props = defineProps<{
  direction: Direction;
  entry: string;
  stop: string;
  target: string;
  stopDistance: string;
  targetDistance: string;
  exitPrice?: string | null;
  realizedPnl?: string | null;
}>();
const { t } = useI18n();

const scale = computed(() =>
  calculatePositionScale(
    props.direction,
    props.entry,
    props.stop,
    props.target,
    props.exitPrice,
  ),
);
const position = (value: number): { left: string } => ({ left: `${value}%` });
const segment = (start: number, end: number) => ({
  left: `${start}%`,
  width: `${end - start}%`,
});
const exitTone = computed(() => {
  if (!props.realizedPnl) return "neutral";
  const pnl = new Decimal(props.realizedPnl);
  return pnl.isPositive() ? "profit" : pnl.isNegative() ? "loss" : "neutral";
});
const exitEdge = computed(() => {
  if (scale.value.exit === null) return null;
  if (scale.value.exit <= 0.5) return "loss";
  if (scale.value.exit >= 99.5) return "profit";
  return null;
});
const entryTooltip = computed(
  () => `${t("trades.plan.entry")} · ${formatDecimal(props.entry)}`,
);
const exitTooltip = computed(() =>
  props.exitPrice
    ? `${scale.value.exitOverflow === "loss" ? "← " : ""}${t(
        "trades.close.exit",
      )} · ${formatDecimal(props.exitPrice)}${
        scale.value.exitOverflow === "profit" ? " →" : ""
      }`
    : "",
);
</script>

<template>
  <div class="position-risk-map">
    <div class="position-risk-map__labels">
      <span class="position-risk-map__price position-risk-map__price--stop">
        <small>{{ $t("trades.plan.stop") }}</small>
        <strong>{{ formatDecimal(stop) }}</strong>
        <em>−{{ formatDecimal(stopDistance) }}</em>
      </span>
      <span class="position-risk-map__price position-risk-map__price--target">
        <small>{{ $t("trades.plan.target") }}</small>
        <strong>{{ formatDecimal(target) }}</strong>
        <em>+{{ formatDecimal(targetDistance) }}</em>
      </span>
    </div>
    <div class="position-risk-map__bar">
      <span
        class="position-risk-map__loss"
        :style="segment(scale.stop, scale.entry)"
      ></span>
      <span
        class="position-risk-map__reward"
        :style="segment(scale.entry, scale.target)"
      ></span>
      <button
        type="button"
        class="position-risk-map__entry-marker"
        :style="position(scale.entry)"
        :aria-label="entryTooltip"
        :data-tooltip="entryTooltip"
      ></button>
      <button
        v-if="scale.exit !== null"
        type="button"
        class="position-risk-map__exit-marker"
        :class="[
          `position-risk-map__exit-marker--${exitTone}`,
          {
            'position-risk-map__exit-marker--overflow': scale.exitOverflow,
            [`position-risk-map__exit-marker--edge-${exitEdge}`]: exitEdge,
          },
        ]"
        :style="position(scale.exit)"
        :aria-label="exitTooltip"
        :data-tooltip="exitTooltip"
      >
        <span></span>
      </button>
    </div>
  </div>
</template>

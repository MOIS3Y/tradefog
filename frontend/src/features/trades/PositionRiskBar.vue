<script setup lang="ts">
import { computed } from "vue";

import { formatDecimal } from "@/utils/decimal";

const props = defineProps<{
  entry: string;
  stop: string;
  target: string;
  stopDistance: string;
  targetDistance: string;
  rewardMultiple: string | number;
}>();

const proportion = computed(() => ({
  gridTemplateColumns: `minmax(0, 1fr) minmax(0, ${props.rewardMultiple}fr)`,
}));
</script>

<template>
  <div class="position-risk-map">
    <div class="position-risk-map__labels">
      <span class="position-risk-map__stop">
        <small>{{ $t("trades.plan.stop") }}</small>
        <strong>{{ formatDecimal(stop) }}</strong>
        <em>−{{ formatDecimal(stopDistance) }}</em>
      </span>
      <span class="position-risk-map__target">
        <small>{{ $t("trades.plan.target") }}</small>
        <strong>{{ formatDecimal(target) }}</strong>
        <em>+{{ formatDecimal(targetDistance) }}</em>
      </span>
    </div>
    <div class="position-risk-map__bar" :style="proportion">
      <span class="position-risk-map__loss"></span>
      <span class="position-risk-map__reward"></span>
      <i></i>
    </div>
    <div class="position-risk-map__entry" :style="proportion">
      <span></span>
      <strong
        >{{ $t("trades.plan.entry") }} · {{ formatDecimal(entry) }}</strong
      >
    </div>
  </div>
</template>

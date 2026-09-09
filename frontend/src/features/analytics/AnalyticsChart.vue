<script setup lang="ts">
import { LineChart, ScatterChart } from "echarts/charts";
import {
  AriaComponent,
  GridComponent,
  MarkLineComponent,
  TooltipComponent,
} from "echarts/components";
import {
  init,
  use,
  type EChartsCoreOption,
  type EChartsType,
} from "echarts/core";
import { CanvasRenderer } from "echarts/renderers";
import { onBeforeUnmount, onMounted, ref, watch } from "vue";

use([
  LineChart,
  ScatterChart,
  GridComponent,
  TooltipComponent,
  MarkLineComponent,
  AriaComponent,
  CanvasRenderer,
]);

const props = defineProps<{
  option: EChartsCoreOption;
  label: string;
}>();
const emit = defineEmits<{ selectTrade: [tradeId: number] }>();

const root = ref<HTMLElement | null>(null);
let chart: EChartsType | null = null;
let resizeObserver: ResizeObserver | null = null;

function tradeIdFromEvent(event: unknown): number | null {
  if (typeof event !== "object" || event === null) return null;
  const data = (event as { data?: unknown }).data;
  if (typeof data !== "object" || data === null) return null;
  const tradeId = (data as { tradeId?: unknown }).tradeId;
  return typeof tradeId === "number" ? tradeId : null;
}

onMounted(() => {
  if (root.value === null) return;
  chart = init(root.value, undefined, { renderer: "canvas" });
  chart.setOption(props.option, true);
  chart.on("click", (event) => {
    const tradeId = tradeIdFromEvent(event);
    if (tradeId !== null) emit("selectTrade", tradeId);
  });
  resizeObserver = new ResizeObserver(() => chart?.resize());
  resizeObserver.observe(root.value);
});

watch(
  () => props.option,
  (option) => chart?.setOption(option, true),
  { deep: true },
);

onBeforeUnmount(() => {
  resizeObserver?.disconnect();
  chart?.dispose();
});
</script>

<template>
  <div ref="root" class="analytics-chart" role="img" :aria-label="label"></div>
</template>

<script setup lang="ts">
/** Removable bridge: market panels surround, but never own, position inputs. */
import { useQueryClient } from "@tanstack/vue-query";
import { computed, defineAsyncComponent } from "vue";
import type {
  Instrument,
  Asset,
  VenueType,
} from "@/features/profiles/marketApi";
import { uploadAttachment } from "./api";
import { useAuthStore } from "@/stores/auth";
import { resolveMarket } from "@/features/market-chart/registry";
import type { MarketInstrument } from "@/features/market-chart/types";

const props = defineProps<{
  tradeId: number;
  instrument?: Instrument;
  venueType?: VenueType;
  base?: Asset;
  quote?: Asset;
}>();
const MarketPanel = defineAsyncComponent(
  () => import("@/features/market-chart/MarketPanel.vue"),
);
const auth = useAuthStore();
const client = useQueryClient();
const context = computed<MarketInstrument | undefined>(() => {
  const i = props.instrument;
  return i && props.base && props.quote
    ? {
        symbol: i.exec_symbol,
        product: i.product,
        base: props.base?.symbol ?? "",
        quote: props.quote?.symbol ?? "",
      }
    : undefined;
});
const adapter = computed(() => resolveMarket(props.venueType, context.value));
const storageKey = computed(
  () =>
    `tradefog:drawings:v1:${auth.user?.id}:${props.tradeId}:${props.instrument?.id}`,
);

/** Reuse private attachments; no market component knows journal API routes. */
async function saveSnapshot(file: File): Promise<void> {
  await uploadAttachment(props.tradeId, file);
  await client.invalidateQueries({
    queryKey: ["trade-attachments", props.tradeId],
  });
}
</script>

<template>
  <div
    class="trade-market-workspace"
    :class="{ 'trade-market-workspace--enabled': adapter && context }"
  >
    <MarketPanel
      v-if="adapter && context"
      :key="`${storageKey}:${adapter.id}:${context.product}:${context.symbol}`"
      :adapter="adapter"
      :instrument="context"
      :storage-key="storageKey"
      :save-snapshot="saveSnapshot"
    />
    <div class="trade-market-workspace__position"><slot /></div>
  </div>
</template>

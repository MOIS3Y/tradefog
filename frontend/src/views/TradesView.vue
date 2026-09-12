<script setup lang="ts">
import PanelHeading from "@/components/PanelHeading.vue";
import { ChartCandlestick } from "@lucide/vue";
import TradeWorkspace from "@/features/trades/TradeWorkspace.vue";
import TradePage from "@/features/trades/TradePage.vue";
import AppShell from "@/layouts/AppShell.vue";
</script>

<template>
  <AppShell>
    <div class="workspace trade-workspace">
      <PanelHeading
        v-if="$route.params.tradeId"
        :icon="ChartCandlestick"
        :title="$t('journal.detail', { id: $route.params.tradeId })"
        :description="$t('pageDescriptions.trade')"
      />
      <TradeWorkspace
        v-if="!$route.params.tradeId"
        :key="`list:${$route.path}`"
      />
      <TradePage v-else :key="`detail:${$route.path}`" />
    </div>
  </AppShell>
</template>

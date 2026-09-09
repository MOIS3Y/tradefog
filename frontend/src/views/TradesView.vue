<script setup lang="ts">
import TradeWorkspace from "@/features/trades/TradeWorkspace.vue";
import AppShell from "@/layouts/AppShell.vue";
</script>

<template>
  <AppShell>
    <div class="workspace trade-workspace">
      <header class="catalog-heading">
        <h1>{{ $t("trades.title") }}</h1>
      </header>
      <TradeWorkspace />
    </div>
  </AppShell>
</template>

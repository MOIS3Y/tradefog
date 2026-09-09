<script setup lang="ts">
import TradeWorkspace from "@/features/trades/TradeWorkspace.vue";
import TradePage from "@/features/trades/TradePage.vue";
import AppShell from "@/layouts/AppShell.vue";
</script>

<template>
  <AppShell>
    <div class="workspace trade-workspace">
      <header class="catalog-heading">
        <h1>
          {{
            $route.path === "/trades"
              ? $t("journal.title")
              : $route.path === "/trades/new"
                ? $t("trades.new")
                : $t("journal.detail", { id: $route.params.tradeId })
          }}
        </h1>
        <p>
          {{
            $t(
              $route.path === "/trades"
                ? "pageDescriptions.trades"
                : $route.path === "/trades/new"
                  ? "pageDescriptions.newTrade"
                  : "pageDescriptions.trade",
            )
          }}
        </p>
      </header>
      <TradeWorkspace v-if="$route.path === '/trades'" />
      <TradePage v-else />
    </div>
  </AppShell>
</template>

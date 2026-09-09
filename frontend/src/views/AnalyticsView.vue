<script setup lang="ts">
import AnalyticsWorkspace from "@/features/analytics/AnalyticsWorkspace.vue";
import AppShell from "@/layouts/AppShell.vue";
</script>

<template>
  <AppShell>
    <div class="workspace analytics-page">
      <header class="catalog-heading analytics-heading">
        <div>
          <h1>{{ $t("analytics.title") }}</h1>
          <p>{{ $t("analytics.subtitle") }}</p>
        </div>
      </header>
      <AnalyticsWorkspace />
    </div>
  </AppShell>
</template>

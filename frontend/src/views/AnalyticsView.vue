<script setup lang="ts">
import PanelHeading from "@/components/PanelHeading.vue";
import { ChartNoAxesCombined } from "@lucide/vue";
import AnalyticsWorkspace from "@/features/analytics/AnalyticsWorkspace.vue";
import AppShell from "@/layouts/AppShell.vue";
</script>

<template>
  <AppShell>
    <div class="workspace analytics-page">
      <PanelHeading
        :icon="ChartNoAxesCombined"
        :title="$t('analytics.title')"
        :description="$t('analytics.subtitle')"
      />
      <AnalyticsWorkspace :key="$route.path" />
    </div>
  </AppShell>
</template>

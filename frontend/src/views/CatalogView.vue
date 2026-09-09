<script setup lang="ts">
import { ArrowLeftRight, Building2, Coins } from "@lucide/vue";
import { computed } from "vue";
import { useI18n } from "vue-i18n";

import AssetCatalog from "@/features/catalog/AssetCatalog.vue";
import PairCatalog from "@/features/catalog/PairCatalog.vue";
import VenueCatalog from "@/features/venues/VenueCatalog.vue";
import AppShell from "@/layouts/AppShell.vue";

const props = defineProps<{ section: "assets" | "pairs" | "venues" }>();
const { t } = useI18n();

const steps = computed(() => [
  {
    label: t("catalog.asset.title"),
    icon: Coins,
    path: "/catalog/assets",
    state: props.section === "assets" ? "active" : "complete",
  },
  {
    label: t("catalog.pair.title"),
    icon: ArrowLeftRight,
    path: "/catalog/pairs",
    state:
      props.section === "pairs"
        ? "active"
        : props.section === "venues"
          ? "complete"
          : "pending",
  },
  {
    label: t("catalog.venues"),
    icon: Building2,
    path: "/catalog/venues",
    state: props.section === "venues" ? "active" : "pending",
  },
]);
</script>

<template>
  <AppShell>
    <div class="workspace catalog-workspace">
      <header class="catalog-heading">
        <h1>{{ $t("catalog.title") }}</h1>
        <p>{{ $t("pageDescriptions.catalog") }}</p>
      </header>

      <ol class="catalog-path" :aria-label="$t('catalog.sequence')">
        <li
          v-for="step in steps"
          :key="step.label"
          :class="`catalog-path__step--${step.state}`"
        >
          <RouterLink v-if="step.path" :to="step.path">
            <component :is="step.icon" :size="18" aria-hidden="true" />
            <strong>{{ step.label }}</strong>
          </RouterLink>
          <span v-else>
            <component :is="step.icon" :size="18" aria-hidden="true" />
            <strong>{{ step.label }}</strong>
          </span>
        </li>
      </ol>

      <AssetCatalog v-if="section === 'assets'" />
      <PairCatalog v-else-if="section === 'pairs'" />
      <VenueCatalog v-else />
    </div>
  </AppShell>
</template>

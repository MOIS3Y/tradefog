<script setup lang="ts">
import { useI18n } from "vue-i18n";

import PanelHeading from "@/components/PanelHeading.vue";
import { LayoutDashboard } from "@lucide/vue";
import AppShell from "@/layouts/AppShell.vue";
import { useAuthStore } from "@/stores/auth";

const auth = useAuthStore();
const { t } = useI18n();
const steps = [
  "dashboard.stepProfile",
  "profileMarket.setupStep",
  "dashboard.stepStrategy",
  "dashboard.stepTrade",
] as const;
</script>

<template>
  <AppShell>
    <div class="workspace">
      <PanelHeading
        :icon="LayoutDashboard"
        :title="$t('dashboard.greeting', { name: auth.user?.username })"
        :description="$t('dashboard.lead')"
      >
        <div class="connection-badge">
          <span aria-hidden="true"></span>
          {{ $t("dashboard.connection") }}
        </div>
      </PanelHeading>

      <section class="setup-card" aria-labelledby="setup-title">
        <div class="setup-card__copy">
          <span class="section-label">{{ $t("dashboard.sequence") }}</span>
          <h2 id="setup-title">{{ $t("dashboard.emptyTitle") }}</h2>
          <p>{{ $t("dashboard.emptyBody") }}</p>
        </div>
        <ol class="setup-sequence">
          <li v-for="(step, index) in steps" :key="step">
            <span class="setup-sequence__number">
              {{ String(index + 1).padStart(2, "0") }}
            </span>
            <span>{{ t(step) }}</span>
          </li>
        </ol>
      </section>

      <section class="discipline-card" aria-labelledby="discipline-title">
        <div class="discipline-card__visual" aria-hidden="true">
          <svg viewBox="0 0 460 120" preserveAspectRatio="none">
            <path
              class="discipline-card__area"
              d="M0 98L42 92L78 96L116 70L154 79L194 58L235 66L278 37L322 54L367 29L414 40L460 18V120H0Z"
            />
            <path
              class="discipline-card__line"
              d="M0 98L42 92L78 96L116 70L154 79L194 58L235 66L278 37L322 54L367 29L414 40L460 18"
            />
          </svg>
          <div class="discipline-card__measure">
            <span>0R</span>
            <span>½R</span>
            <span>1R</span>
          </div>
        </div>
        <div>
          <p id="discipline-title" class="section-label">
            {{ $t("dashboard.discipline") }}
          </p>
          <blockquote>{{ $t("dashboard.maxim") }}</blockquote>
        </div>
      </section>
    </div>
  </AppShell>
</template>

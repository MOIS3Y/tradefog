<script setup lang="ts">
import { CircleHelp, X } from "@lucide/vue";
import {
  PopoverClose,
  PopoverContent,
  PopoverPortal,
  PopoverRoot,
  PopoverTrigger,
} from "reka-ui";
import { useI18n } from "vue-i18n";

import {
  analyticsHelp,
  type AnalyticsHelpKey,
} from "@/features/analytics/help";

defineProps<{ topic: AnalyticsHelpKey; label: string }>();
const { locale } = useI18n();
</script>

<template>
  <span class="metric-label">
    {{ label }}
    <PopoverRoot>
      <PopoverTrigger class="metric-help-trigger" :aria-label="label">
        <CircleHelp :size="14" aria-hidden="true" />
      </PopoverTrigger>
      <PopoverPortal to=".tf-app">
        <PopoverContent
          class="metric-help-content"
          :side-offset="8"
          :collision-padding="16"
          :aria-label="label"
        >
          <strong>{{ label }}</strong>
          <PopoverClose
            class="metric-help-close"
            :aria-label="$t('common.close')"
          >
            <X :size="16" aria-hidden="true" />
          </PopoverClose>
          <p>{{ analyticsHelp[topic][locale === "ru" ? "ru" : "en"] }}</p>
        </PopoverContent>
      </PopoverPortal>
    </PopoverRoot>
  </span>
</template>

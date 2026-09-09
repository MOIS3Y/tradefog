<script setup lang="ts">
import { Star } from "@lucide/vue";
import { computed } from "vue";
import { useI18n } from "vue-i18n";
const props = defineProps<{ value: number | null }>();
const { t } = useI18n();
const label = computed(() =>
  props.value === null
    ? t("trades.rating.empty")
    : t("trades.rating.value", { value: props.value, maximum: 10 }),
);
</script>

<template>
  <span class="journal-stars" role="img" :aria-label="label" :title="label">
    <span v-for="slot in 5" :key="slot" class="journal-star" aria-hidden="true">
      <Star :size="16" /><span
        :style="{
          width: `${Math.max(0, Math.min(2, (value ?? 0) - (slot - 1) * 2)) * 50}%`,
        }"
        ><Star :size="16"
      /></span>
    </span>
  </span>
</template>

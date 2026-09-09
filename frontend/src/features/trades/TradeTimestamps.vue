<script setup lang="ts">
import { computed } from "vue";
import { useI18n } from "vue-i18n";
import type { Trade } from "@/features/trades/api";
import { formatDateTime, utcTimestamp } from "@/utils/datetime";

const fields = [
  "created_at",
  "submitted_at",
  "opened_at",
  "closed_at",
  "cancelled_at",
] as const;
const props = defineProps<{ trade: Pick<Trade, (typeof fields)[number]> }>();
const { locale } = useI18n();
const events = computed(() =>
  fields.flatMap((key) => {
    const value = props.trade[key];
    return value ? [{ key, value }] : [];
  }),
);
</script>

<template>
  <section class="trade-times" :aria-label="$t('tradeTimes.label')">
    <span class="trade-times__caption">{{ $t("tradeTimes.label") }}</span>
    <dl>
      <div v-for="event in events" :key="event.key">
        <dt>{{ $t(`tradeTimes.${event.key}`) }}</dt>
        <dd>
          <time :datetime="utcTimestamp(event.value)">{{
            formatDateTime(event.value, locale)
          }}</time>
        </dd>
      </div>
    </dl>
  </section>
</template>

<style scoped>
.trade-times {
  padding: 0.85rem 1.5rem;
  border-bottom: 1px solid var(--tf-line-soft);
  color: var(--tf-ink-soft);
  font-size: 0.75rem;
}
.trade-times__caption {
  font-size: 0.7rem;
}
dl {
  display: flex;
  flex-wrap: wrap;
  gap: 0.65rem 1.5rem;
  margin: 0.5rem 0 0;
}
dt {
  margin-bottom: 0.2rem;
}
dd {
  margin: 0;
  color: var(--tf-ink);
  font-family: var(--tf-mono);
  font-variant-numeric: tabular-nums;
}
time {
  white-space: nowrap;
}
</style>

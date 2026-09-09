<script setup lang="ts">
import { computed } from "vue";
import { ChevronLeft, ChevronRight } from "@lucide/vue";
import { useI18n } from "vue-i18n";
import AppSelect from "@/components/AppSelect.vue";

const props = defineProps<{
  page: number;
  pageSize: number;
  total: number;
  busy?: boolean;
  compact?: boolean;
  hideWhenSmall?: boolean;
}>();
const emit = defineEmits<{
  "update:page": [number];
  "update:pageSize": [number];
}>();
const { t } = useI18n();
const pages = computed(() =>
  Math.max(1, Math.ceil(props.total / props.pageSize)),
);
const minimumPageSize = 25;
const visible = computed(
  () =>
    !props.hideWhenSmall ||
    props.total > minimumPageSize ||
    props.pageSize !== minimumPageSize,
);
const sizes = [minimumPageSize, 50, 100].map((value) => ({
  value: String(value),
  label: String(value),
}));
</script>

<template>
  <nav
    v-if="visible"
    class="pagination"
    :class="{ 'pagination--compact': compact }"
    :aria-label="t('pagination.label')"
  >
    <span>{{ t("pagination.summary", { page, pages, total }) }}</span>
    <div class="pagination__controls">
      <AppSelect
        :model-value="String(pageSize)"
        :options="sizes"
        :label="t('pagination.size')"
        @update:model-value="emit('update:pageSize', Number($event))"
      />
      <button
        class="button button--secondary pagination__arrow"
        type="button"
        :aria-label="t('pagination.previous')"
        :title="t('pagination.previous')"
        :disabled="busy || page <= 1"
        @click="emit('update:page', page - 1)"
      >
        <ChevronLeft :size="18" aria-hidden="true" />
      </button>
      <button
        class="button button--secondary pagination__arrow"
        type="button"
        :aria-label="t('pagination.next')"
        :title="t('pagination.next')"
        :disabled="busy || page >= pages"
        @click="emit('update:page', page + 1)"
      >
        <ChevronRight :size="18" aria-hidden="true" />
      </button>
    </div>
  </nav>
</template>

<style scoped>
.pagination {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: flex-end;
  gap: 0.7rem;
  padding: 1rem;
  color: var(--tf-ink-soft);
  font-size: 0.75rem;
}
.pagination > span {
  margin-right: auto;
}
.pagination__controls {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  flex-shrink: 0;
}
.pagination--compact > span {
  flex-basis: 100%;
}
.pagination--compact .pagination__controls {
  width: 100%;
}
.pagination--compact :deep(.tf-select-trigger) {
  margin-right: auto;
}
.pagination .pagination__arrow {
  width: 36px;
  min-height: 36px;
  padding: 0;
}
.pagination :deep(.tf-select-trigger) {
  width: 76px;
  min-width: 76px;
}
</style>

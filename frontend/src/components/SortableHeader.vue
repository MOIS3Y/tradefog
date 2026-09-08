<script setup lang="ts">
import { ArrowDown, ArrowUp, ArrowUpDown } from "@lucide/vue";
import { computed } from "vue";

import type { SortDirection } from "@/features/catalog/filters";

const props = defineProps<{
  label: string;
  direction?: SortDirection | null;
}>();

const emit = defineEmits<{
  sort: [];
}>();

const ariaSort = computed(() => {
  if (props.direction === "asc") {
    return "ascending";
  }
  if (props.direction === "desc") {
    return "descending";
  }
  return undefined;
});
</script>

<template>
  <th :aria-sort="ariaSort">
    <button
      :class="['catalog-sort', { 'catalog-sort--active': direction }]"
      type="button"
      @click="emit('sort')"
    >
      <span>{{ label }}</span>
      <ArrowUp v-if="direction === 'asc'" :size="13" aria-hidden="true" />
      <ArrowDown
        v-else-if="direction === 'desc'"
        :size="13"
        aria-hidden="true"
      />
      <ArrowUpDown v-else :size="13" aria-hidden="true" />
    </button>
  </th>
</template>

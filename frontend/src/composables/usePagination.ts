/** Reset pages when their criteria change and recover after row removal. */
import { computed, ref, watch, type ComputedRef } from "vue";
import type { Page } from "@/api/pagination";

export function usePagination(criteria: ComputedRef<unknown>) {
  const page = ref(1);
  const pageSize = ref(25);
  watch(
    [criteria, pageSize],
    () => {
      page.value = 1;
    },
    { flush: "sync" },
  );
  const params = computed(() => ({
    page: page.value,
    page_size: pageSize.value,
  }));
  function track<T>(data: ComputedRef<Page<T> | undefined>): void {
    watch(data, (value) => {
      if (!value) return;
      const last = Math.max(1, Math.ceil(value.total / value.page_size));
      if (page.value > last) page.value = last;
    });
  }
  return { page, pageSize, params, track };
}

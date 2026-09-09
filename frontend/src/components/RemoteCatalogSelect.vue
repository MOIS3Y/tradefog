<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from "vue";
import { useInfiniteQuery, useQuery } from "@tanstack/vue-query";
import { useI18n } from "vue-i18n";
import { authenticatedFetch } from "@/api/client";
import { toApiError } from "@/api/errors";
import type { Page, ListParams } from "@/api/pagination";
import type { Asset, Pair } from "@/features/catalog/api";
import type {
  Instrument,
  Venue,
  VenueWalletAsset,
} from "@/features/venues/api";
import SearchableSelect, {
  type SearchableOption,
} from "@/components/SearchableSelect.vue";

type Item = Asset | Pair | Instrument | Venue | VenueWalletAsset;
const props = defineProps<{
  modelValue: number | null;
  resource: "assets" | "pairs" | "venues" | "instruments" | "wallet-assets";
  venueId?: number;
  params?: ListParams;
  excludeId?: number | null;
  placeholder: string;
  emptyLabel: string;
  disabled?: boolean;
  extraOptions?: SearchableOption[];
}>();
const emit = defineEmits<{ "update:modelValue": [number | null] }>();
const { t } = useI18n();
const search = ref("");
const debounced = ref("");
const open = ref(false);
let timer: ReturnType<typeof setTimeout> | undefined;
watch(search, (value) => {
  clearTimeout(timer);
  timer = setTimeout(() => {
    debounced.value = value;
  }, 250);
});
onBeforeUnmount(() => clearTimeout(timer));
const collection = computed(() =>
  props.venueId && ["instruments", "wallet-assets"].includes(props.resource)
    ? `/api/v1/catalog/venues/${props.venueId}/${props.resource}`
    : `/api/v1/catalog/${props.resource}`,
);

async function read<T>(
  path: string,
  params: Record<string, unknown> = {},
): Promise<T> {
  const url = new URL(path, window.location.origin);
  for (const [key, value] of Object.entries(params)) {
    if (Array.isArray(value)) {
      for (const item of value) url.searchParams.append(key, String(item));
      continue;
    }
    if (value !== undefined && value !== null)
      url.searchParams.set(key, String(value));
  }
  const response = await authenticatedFetch(new Request(url));
  const data: unknown = await response.json();
  if (!response.ok) throw toApiError(data, response);
  return data as T;
}

const query = useInfiniteQuery({
  queryKey: computed(() => [
    "catalog",
    props.resource,
    "options",
    collection.value,
    props.params,
    debounced.value,
  ]),
  enabled: computed(() => open.value && !props.disabled),
  initialPageParam: 1,
  queryFn: ({ pageParam }) =>
    read<Page<Item>>(collection.value, {
      ...props.params,
      q: debounced.value,
      page: pageParam,
      page_size: 25,
    }),
  getNextPageParam: (last) =>
    last.page * last.page_size < last.total ? last.page + 1 : undefined,
});
const selectedQuery = useQuery({
  queryKey: computed(() => [
    "catalog",
    "option",
    props.resource,
    props.modelValue,
  ]),
  enabled: computed(() => props.modelValue !== null && props.modelValue > 0),
  queryFn: () =>
    read<Item>(`/api/v1/catalog/${props.resource}/${props.modelValue}`),
});
function option(item: Item): SearchableOption {
  if ("exec_symbol" in item)
    return {
      value: item.id,
      label: item.pair.canonical_symbol,
      detail: `${item.exec_symbol} · ${t(`venues.products.${item.product}`)}`,
    };
  if ("canonical_symbol" in item)
    return { value: item.id, label: item.canonical_symbol };
  if ("asset" in item)
    return {
      value: item.id,
      label: item.asset.symbol,
      detail: item.asset.name ?? undefined,
    };
  if ("symbol" in item)
    return {
      value: item.id,
      label: item.symbol,
      detail: item.name ?? undefined,
    };
  return { value: item.id, label: item.name };
}
const options = computed(() => {
  const items = query.data.value?.pages.flatMap((page) => page.items) ?? [];
  if (selectedQuery.data.value) items.unshift(selectedQuery.data.value);
  const all = [...(props.extraOptions ?? []), ...items.map(option)];
  return [
    ...new Map(
      all.filter((x) => x.value !== props.excludeId).map((x) => [x.value, x]),
    ).values(),
  ];
});
</script>

<template>
  <SearchableSelect
    :model-value="modelValue"
    :options="options"
    :placeholder="placeholder"
    :empty-label="query.isFetching.value ? t('pagination.loading') : emptyLabel"
    :disabled="disabled"
    remote
    :has-more="query.hasNextPage.value"
    :busy="query.isFetching.value"
    :error="query.isError.value || selectedQuery.isError.value"
    @update:model-value="emit('update:modelValue', $event)"
    @search="search = $event"
    @open="open = $event"
    @load-more="query.fetchNextPage()"
    @retry="
      query.refetch();
      selectedQuery.refetch();
    "
  />
</template>

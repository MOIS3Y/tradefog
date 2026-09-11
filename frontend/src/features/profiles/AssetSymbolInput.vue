<script setup lang="ts">
/** Select a profile symbol or explicitly create a new denomination. */
import { computed, ref, watch } from "vue";
import { useInfiniteQuery } from "@tanstack/vue-query";
import { useI18n } from "vue-i18n";
import SearchableSelect from "@/components/SearchableSelect.vue";
import AppSelect from "@/components/AppSelect.vue";
import { listAssets, type Asset } from "./marketApi";

const props = defineProps<{
  profileId: number;
  label: string;
  disabled?: boolean;
}>();
const symbol = defineModel<string>({ required: true });
const assetType = defineModel<Asset["asset_type"] | undefined>("assetType");
const { t } = useI18n();
const search = ref("");
const debounced = ref("");
watch(search, (value, _, cleanup) => {
  const timer = setTimeout(() => {
    debounced.value = value;
  }, 250);
  cleanup(() => clearTimeout(timer));
});
const query = useInfiniteQuery({
  queryKey: computed(() => [
    "profile-market",
    props.profileId,
    "asset-symbols",
    debounced.value,
  ]),
  initialPageParam: 1,
  queryFn: ({ pageParam }) =>
    listAssets(props.profileId, {
      page: pageParam,
      page_size: 25,
      q: debounced.value,
      visibility: "all",
    }),
  getNextPageParam: (last) =>
    last.page * last.page_size < last.total ? last.page + 1 : undefined,
});
const items = computed(
  () => query.data.value?.pages.flatMap((page) => page.items) ?? [],
);
const normalized = computed(() => search.value.trim().toUpperCase());
const options = computed(() => [
  ...(symbol.value ? [{ value: 0, label: symbol.value }] : []),
  ...items.value
    .filter((item) => item.symbol !== symbol.value)
    .map((item) => ({
      value: item.id,
      label: item.symbol,
      detail: item.is_archived
        ? t("profiles.archivedState")
        : (item.name ?? undefined),
      disabled: item.is_archived,
    })),
  ...(normalized.value &&
  !items.value.some((item) => item.symbol === normalized.value) &&
  normalized.value !== symbol.value &&
  !query.isFetching.value
    ? [
        {
          value: -1,
          label: t("profileMarket.createSymbol", { symbol: normalized.value }),
        },
      ]
    : []),
]);
const types = computed(() =>
  ["crypto", "fiat", "equity"].map((value) => ({
    value: value as Asset["asset_type"],
    label: t(`catalog.types.${value}`),
  })),
);
function select(value: number | null): void {
  if (value === 0) return;
  symbol.value =
    value === -1
      ? normalized.value
      : (items.value.find((item) => item.id === value)?.symbol ?? "");
  assetType.value = value === -1 ? "crypto" : undefined;
}
</script>

<template>
  <div class="field asset-symbol-field">
    <span>{{ label }}</span>
    <SearchableSelect
      :model-value="symbol ? 0 : null"
      :options="options"
      :placeholder="label"
      :empty-label="$t('catalog.noResults')"
      remote
      :disabled="disabled"
      :busy="query.isFetching.value"
      :error="query.isError.value"
      :has-more="query.hasNextPage.value"
      @search="search = $event"
      @update:model-value="select"
      @load-more="query.fetchNextPage()"
      @retry="query.refetch()"
    />
    <AppSelect
      v-if="assetType && !disabled"
      v-model="assetType"
      :options="types"
      :label="$t('profileMarket.assetType')"
    />
  </div>
</template>

<script setup lang="ts">
import { Coins, Pencil, Plus, Search, Trash2 } from "@lucide/vue";
import { computed, reactive, ref } from "vue";
import { useMutation, useQuery, useQueryClient } from "@tanstack/vue-query";
import { useI18n } from "vue-i18n";

import { ApiError } from "@/api/errors";
import AppSelect, { type SelectOption } from "@/components/AppSelect.vue";
import ConfirmDialog from "@/components/ConfirmDialog.vue";
import EmptyState from "@/components/EmptyState.vue";
import ErrorState from "@/components/ErrorState.vue";
import FormDialog from "@/components/FormDialog.vue";
import LoadingState from "@/components/LoadingState.vue";
import SortableHeader from "@/components/SortableHeader.vue";
import {
  createAsset,
  deleteAsset,
  listAssets,
  updateAsset,
  type Asset,
  type AssetType,
  type AssetWrite,
} from "@/features/catalog/api";
import {
  filterAssets,
  sortAssets,
  type AssetSortKey,
  type SortDirection,
} from "@/features/catalog/filters";
import { useAuthStore } from "@/stores/auth";
import { useToastStore } from "@/stores/toasts";

const auth = useAuthStore();
const toasts = useToastStore();
const queryClient = useQueryClient();
const { t } = useI18n();

const search = ref("");
const typeFilter = ref<AssetType | "all">("all");
const sortKey = ref<AssetSortKey>("symbol");
const sortDirection = ref<SortDirection>("asc");
const dialogOpen = ref(false);
const editing = ref<Asset | null>(null);
const deleteTarget = ref<Asset | null>(null);
const form = reactive<AssetWrite>({
  symbol: "",
  name: null,
  asset_type: "crypto",
});

const query = useQuery({
  queryKey: ["catalog", "assets"],
  queryFn: listAssets,
});
const assets = computed(() => query.data.value ?? []);
const filtered = computed(() =>
  sortAssets(
    filterAssets(assets.value, search.value, typeFilter.value),
    sortKey.value,
    sortDirection.value,
  ),
);
const formInvalid = computed(() => form.symbol.trim().length === 0);
const assetTypeOptions = computed<SelectOption<AssetType>[]>(() => [
  { value: "crypto", label: t("catalog.types.crypto") },
  { value: "fiat", label: t("catalog.types.fiat") },
  { value: "equity", label: t("catalog.types.equity") },
]);
const filterTypeOptions = computed<SelectOption<AssetType | "all">[]>(() => [
  { value: "all", label: t("catalog.allTypes") },
  ...assetTypeOptions.value,
]);

function showError(error: unknown, context: "save" | "delete"): void {
  const apiError = error instanceof ApiError ? error : null;
  const description =
    apiError?.code === "asset_in_use"
      ? t("catalog.errors.assetInUse")
      : apiError?.code === "validation_error"
        ? t("catalog.errors.validation")
        : context === "save" && apiError?.code === "conflict"
          ? t("catalog.errors.assetConflict")
          : t("catalog.errors.unavailable");
  toasts.error({
    title: t(
      context === "save"
        ? "catalog.asset.saveFailed"
        : "catalog.asset.deleteFailed",
    ),
    description,
  });
}

const saveMutation = useMutation({
  mutationFn: () =>
    editing.value === null
      ? createAsset(form)
      : updateAsset(editing.value.id, form),
  onSuccess: async () => {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ["catalog", "assets"] }),
      queryClient.invalidateQueries({ queryKey: ["catalog", "pairs"] }),
    ]);
    toasts.success({
      title: t(
        editing.value === null
          ? "catalog.asset.created"
          : "catalog.asset.saved",
      ),
    });
    dialogOpen.value = false;
  },
  onError: (error) => showError(error, "save"),
});

const removeMutation = useMutation({
  mutationFn: (asset: Asset) => deleteAsset(asset.id),
  onSuccess: async (_, asset) => {
    await queryClient.invalidateQueries({ queryKey: ["catalog", "assets"] });
    toasts.success({
      title: t("catalog.asset.deleted"),
      description: asset.symbol,
    });
    deleteTarget.value = null;
  },
  onError: (error) => showError(error, "delete"),
});

function openCreate(): void {
  editing.value = null;
  Object.assign(form, { symbol: "", name: null, asset_type: "crypto" });
  dialogOpen.value = true;
}

function openEdit(asset: Asset): void {
  editing.value = asset;
  Object.assign(form, {
    symbol: asset.symbol,
    name: asset.name,
    asset_type: asset.asset_type,
  });
  dialogOpen.value = true;
}

function resetFilters(): void {
  search.value = "";
  typeFilter.value = "all";
}

function toggleSort(key: AssetSortKey): void {
  if (sortKey.value === key) {
    sortDirection.value = sortDirection.value === "asc" ? "desc" : "asc";
    return;
  }
  sortKey.value = key;
  sortDirection.value = "asc";
}

function activeDirection(key: AssetSortKey): SortDirection | null {
  return sortKey.value === key ? sortDirection.value : null;
}
</script>

<template>
  <section class="catalog-section" aria-labelledby="assets-title">
    <header class="catalog-section__header">
      <div>
        <h2 id="assets-title" class="catalog-section__title">
          <Coins :size="21" aria-hidden="true" />
          {{ $t("catalog.asset.title") }}
        </h2>
        <p class="catalog-section__description">
          {{ $t("catalog.asset.description") }}
        </p>
      </div>
      <button
        v-if="auth.user?.is_staff"
        class="button button--primary"
        type="button"
        @click="openCreate"
      >
        <Plus :size="17" aria-hidden="true" />
        {{ $t("catalog.asset.create") }}
      </button>
    </header>

    <div class="catalog-toolbar" role="search">
      <label class="search-field">
        <span class="sr-only">{{ $t("catalog.searchAssets") }}</span>
        <Search class="search-field__icon" :size="16" aria-hidden="true" />
        <input
          v-model="search"
          type="search"
          :placeholder="$t('catalog.searchAssets')"
        />
      </label>
      <AppSelect
        v-model="typeFilter"
        :options="filterTypeOptions"
        :label="$t('catalog.asset.type')"
      />
      <button
        v-if="search || typeFilter !== 'all'"
        class="button-link"
        type="button"
        @click="resetFilters"
      >
        {{ $t("catalog.reset") }}
      </button>
      <span class="catalog-toolbar__count"
        >{{ filtered.length }} / {{ assets.length }}</span
      >
    </div>

    <LoadingState
      v-if="query.isPending.value"
      :label="$t('catalog.loadingAssets')"
    />
    <ErrorState
      v-else-if="query.isError.value"
      :title="$t('catalog.loadFailed')"
      :description="$t('catalog.errors.unavailable')"
      @retry="query.refetch()"
    />
    <EmptyState
      v-else-if="assets.length === 0"
      :title="$t('catalog.asset.emptyTitle')"
    >
      <template #icon><Coins :size="24" /></template>
      <button
        v-if="auth.user?.is_staff"
        class="button button--primary"
        type="button"
        @click="openCreate"
      >
        <Plus :size="17" aria-hidden="true" />
        {{ $t("catalog.asset.createFirst") }}
      </button>
    </EmptyState>
    <div v-else-if="filtered.length === 0" class="catalog-no-results">
      <Search :size="22" aria-hidden="true" />
      <p>{{ $t("catalog.noResults") }}</p>
      <button class="button-link" type="button" @click="resetFilters">
        {{ $t("catalog.reset") }}
      </button>
    </div>
    <div v-else class="catalog-table-wrap">
      <table class="catalog-table">
        <thead>
          <tr>
            <SortableHeader
              :label="$t('catalog.asset.symbol')"
              :direction="activeDirection('symbol')"
              @sort="toggleSort('symbol')"
            />
            <SortableHeader
              :label="$t('catalog.asset.name')"
              :direction="activeDirection('name')"
              @sort="toggleSort('name')"
            />
            <SortableHeader
              :label="$t('catalog.asset.type')"
              :direction="activeDirection('asset_type')"
              @sort="toggleSort('asset_type')"
            />
            <th v-if="auth.user?.is_staff" class="catalog-table__actions">
              <span class="sr-only">{{ $t("catalog.actions") }}</span>
            </th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="asset in filtered" :key="asset.id">
            <td :data-label="$t('catalog.asset.symbol')">
              <strong class="catalog-symbol">{{ asset.symbol }}</strong>
            </td>
            <td :data-label="$t('catalog.asset.name')">
              {{ asset.name || "—" }}
            </td>
            <td :data-label="$t('catalog.asset.type')">
              <span
                :class="['catalog-tag', `catalog-tag--${asset.asset_type}`]"
              >
                {{ $t(`catalog.types.${asset.asset_type}`) }}
              </span>
            </td>
            <td v-if="auth.user?.is_staff" class="catalog-row-actions">
              <button
                class="icon-action"
                type="button"
                :aria-label="$t('catalog.edit')"
                @click="openEdit(asset)"
              >
                <Pencil :size="15" aria-hidden="true" />
              </button>
              <button
                class="icon-action icon-action--danger"
                type="button"
                :aria-label="$t('catalog.delete')"
                @click="deleteTarget = asset"
              >
                <Trash2 :size="15" aria-hidden="true" />
              </button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <FormDialog
      v-model:open="dialogOpen"
      :title="
        $t(editing ? 'catalog.asset.editTitle' : 'catalog.asset.createTitle')
      "
      :description="$t('catalog.asset.formDescription')"
      :submit-label="
        $t(editing ? 'catalog.saveChanges' : 'catalog.asset.create')
      "
      :cancel-label="$t('common.cancel')"
      :busy="saveMutation.isPending.value"
      :invalid="formInvalid"
      @submit="saveMutation.mutate()"
    >
      <label class="field">
        <span>{{ $t("catalog.asset.symbol") }}</span>
        <input
          v-model="form.symbol"
          maxlength="32"
          autocomplete="off"
          placeholder="BTC"
          required
        />
        <small>{{ $t("catalog.asset.symbolHint") }}</small>
      </label>
      <label class="field">
        <span>{{ $t("catalog.asset.name") }}</span>
        <input
          v-model="form.name"
          maxlength="255"
          autocomplete="off"
          :placeholder="$t('catalog.asset.namePlaceholder')"
        />
      </label>
      <label class="field">
        <span>{{ $t("catalog.asset.type") }}</span>
        <AppSelect
          v-model="form.asset_type"
          :options="assetTypeOptions"
          :label="$t('catalog.asset.type')"
        />
      </label>
    </FormDialog>

    <ConfirmDialog
      :open="deleteTarget !== null"
      :title="$t('catalog.asset.deleteTitle')"
      :description="
        $t('catalog.asset.deleteBody', { symbol: deleteTarget?.symbol })
      "
      :confirm-label="$t('catalog.delete')"
      :cancel-label="$t('common.cancel')"
      :busy="removeMutation.isPending.value"
      @update:open="!$event && (deleteTarget = null)"
      @confirm="deleteTarget && removeMutation.mutate(deleteTarget)"
    />
  </section>
</template>

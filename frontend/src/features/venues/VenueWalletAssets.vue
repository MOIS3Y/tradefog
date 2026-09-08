<script setup lang="ts">
import {
  Archive,
  ArchiveRestore,
  Coins,
  Plus,
  Search,
  Trash2,
} from "@lucide/vue";
import { useMutation, useQuery, useQueryClient } from "@tanstack/vue-query";
import { computed, ref } from "vue";
import { useI18n } from "vue-i18n";
import { useRouter } from "vue-router";

import { ApiError } from "@/api/errors";
import AppSelect, { type SelectOption } from "@/components/AppSelect.vue";
import ConfirmDialog from "@/components/ConfirmDialog.vue";
import EmptyState from "@/components/EmptyState.vue";
import ErrorState from "@/components/ErrorState.vue";
import FormDialog from "@/components/FormDialog.vue";
import LoadingState from "@/components/LoadingState.vue";
import SearchableSelect, {
  type SearchableOption,
} from "@/components/SearchableSelect.vue";
import SortableHeader from "@/components/SortableHeader.vue";
import { listAssets } from "@/features/catalog/api";
import {
  createVenueWalletAsset,
  deleteVenueWalletAsset,
  listVenueWalletAssets,
  updateVenueWalletAsset,
  type Venue,
  type VenueWalletAsset,
} from "@/features/venues/api";
import {
  filterWalletAssets,
  sortWalletAssets,
  type VisibilityFilter,
  type WalletAssetSortKey,
} from "@/features/venues/filters";
import { useAuthStore } from "@/stores/auth";
import { useToastStore } from "@/stores/toasts";
import type { SortDirection } from "@/utils/sorting";

const props = defineProps<{ venue: Venue }>();
const auth = useAuthStore();
const toasts = useToastStore();
const router = useRouter();
const queryClient = useQueryClient();
const { t } = useI18n();

const search = ref("");
const visibility = ref<VisibilityFilter>("active");
const sortKey = ref<WalletAssetSortKey>("symbol");
const sortDirection = ref<SortDirection>("asc");
const dialogOpen = ref(false);
const assetId = ref<number | null>(null);
const deleteTarget = ref<VenueWalletAsset | null>(null);

const queryKey = computed(() => [
  "catalog",
  "venues",
  props.venue.id,
  "wallet-assets",
]);
const query = useQuery({
  queryKey,
  queryFn: () => listVenueWalletAssets(props.venue.id),
});
const assetsQuery = useQuery({
  queryKey: ["catalog", "assets"],
  queryFn: listAssets,
});
const capabilities = computed(() => query.data.value ?? []);
const assets = computed(() => assetsQuery.data.value ?? []);
const availableAssets = computed(() => {
  const assigned = new Set(
    capabilities.value.map((capability) => capability.asset.id),
  );
  return assets.value.filter((asset) => !assigned.has(asset.id));
});
const assetOptions = computed<SearchableOption[]>(() =>
  availableAssets.value.map((asset) => ({
    value: asset.id,
    label: asset.symbol,
    detail: asset.name ?? t(`catalog.types.${asset.asset_type}`),
  })),
);
const filtered = computed(() =>
  sortWalletAssets(
    filterWalletAssets(capabilities.value, search.value, visibility.value),
    sortKey.value,
    sortDirection.value,
  ),
);
const visibilityOptions = computed<SelectOption<VisibilityFilter>[]>(() => [
  { value: "active", label: t("venues.visibility.active") },
  { value: "archived", label: t("venues.visibility.archived") },
  { value: "all", label: t("venues.visibility.all") },
]);

function showError(error: unknown, action: "save" | "delete"): void {
  const apiError = error instanceof ApiError ? error : null;
  const description =
    apiError?.code === "wallet_asset_in_use"
      ? t("venues.walletAssets.errors.inUse")
      : apiError?.code === "wallet_asset_not_archived"
        ? t("venues.walletAssets.errors.notArchived")
        : apiError?.code === "conflict"
          ? t("venues.walletAssets.errors.conflict")
          : t("catalog.errors.unavailable");
  toasts.error({
    title: t(
      action === "save"
        ? "venues.walletAssets.saveFailed"
        : "venues.walletAssets.deleteFailed",
    ),
    description,
  });
}

const createMutation = useMutation({
  mutationFn: () => createVenueWalletAsset(props.venue.id, assetId.value ?? 0),
  onSuccess: async (capability) => {
    await queryClient.invalidateQueries({
      queryKey: ["catalog", "venues", capability.venue_id, "wallet-assets"],
    });
    toasts.success({
      title: t("venues.walletAssets.created"),
      description: capability.asset.symbol,
    });
    dialogOpen.value = false;
  },
  onError: (error) => showError(error, "save"),
});

const statusMutation = useMutation({
  mutationFn: (capability: VenueWalletAsset) =>
    updateVenueWalletAsset(capability.id, !capability.is_active),
  onSuccess: async (capability) => {
    await queryClient.invalidateQueries({
      queryKey: ["catalog", "venues", capability.venue_id, "wallet-assets"],
    });
    toasts.success({
      title: t(
        capability.is_active
          ? "venues.walletAssets.restored"
          : "venues.walletAssets.archived",
      ),
      description: capability.asset.symbol,
    });
  },
  onError: (error) => showError(error, "save"),
});

const removeMutation = useMutation({
  mutationFn: (capability: VenueWalletAsset) =>
    deleteVenueWalletAsset(capability.id),
  onSuccess: async (_, capability) => {
    await queryClient.invalidateQueries({ queryKey: queryKey.value });
    toasts.success({
      title: t("venues.walletAssets.deleted"),
      description: capability.asset.symbol,
    });
    deleteTarget.value = null;
  },
  onError: (error) => showError(error, "delete"),
});

function openCreate(): void {
  if (assets.value.length === 0) {
    void router.push("/catalog/assets");
    return;
  }
  if (availableAssets.value.length === 0) {
    return;
  }
  assetId.value = null;
  dialogOpen.value = true;
}

function createLabel(): string {
  if (assets.value.length === 0) {
    return t("venues.walletAssets.addResource");
  }
  if (availableAssets.value.length === 0) {
    return t("venues.walletAssets.allAdded");
  }
  return t("venues.walletAssets.create");
}

function resetFilters(): void {
  search.value = "";
  visibility.value = "active";
}

async function retryQueries(): Promise<void> {
  await Promise.all([query.refetch(), assetsQuery.refetch()]);
}

function toggleSort(key: WalletAssetSortKey): void {
  if (sortKey.value === key) {
    sortDirection.value = sortDirection.value === "asc" ? "desc" : "asc";
    return;
  }
  sortKey.value = key;
  sortDirection.value = "asc";
}

function activeDirection(key: WalletAssetSortKey): SortDirection | null {
  return sortKey.value === key ? sortDirection.value : null;
}
</script>

<template>
  <section class="venue-subsection" aria-labelledby="wallet-assets-title">
    <header class="venue-subsection__header">
      <div>
        <h4 id="wallet-assets-title">
          <Coins :size="18" aria-hidden="true" />
          {{ $t("venues.walletAssets.title") }}
        </h4>
        <p>{{ $t("venues.walletAssets.description") }}</p>
      </div>
      <button
        v-if="auth.user?.is_staff"
        class="button button--secondary"
        type="button"
        :disabled="
          assets.length > 0 &&
          availableAssets.length === 0 &&
          !assetsQuery.isPending.value
        "
        @click="openCreate"
      >
        <Plus :size="16" aria-hidden="true" />
        {{ createLabel() }}
      </button>
    </header>

    <div class="venue-subsection__toolbar" role="search">
      <label class="search-field">
        <span class="sr-only">{{ $t("venues.walletAssets.search") }}</span>
        <Search class="search-field__icon" :size="16" aria-hidden="true" />
        <input
          v-model="search"
          type="search"
          :placeholder="$t('venues.walletAssets.search')"
        />
      </label>
      <AppSelect
        v-model="visibility"
        :options="visibilityOptions"
        :label="$t('venues.status')"
      />
      <button
        v-if="search || visibility !== 'active'"
        class="button-link"
        type="button"
        @click="resetFilters"
      >
        {{ $t("catalog.reset") }}
      </button>
      <span class="catalog-toolbar__count">
        {{ filtered.length }} / {{ capabilities.length }}
      </span>
    </div>

    <LoadingState
      v-if="query.isPending.value || assetsQuery.isPending.value"
      :label="$t('venues.walletAssets.loading')"
    />
    <ErrorState
      v-else-if="query.isError.value || assetsQuery.isError.value"
      :title="$t('venues.walletAssets.loadFailed')"
      :description="$t('catalog.errors.unavailable')"
      @retry="retryQueries"
    />
    <EmptyState
      v-else-if="capabilities.length === 0"
      :title="$t('venues.walletAssets.emptyTitle')"
    >
      <template #icon><Coins :size="23" /></template>
      <button
        v-if="auth.user?.is_staff"
        class="button button--secondary"
        type="button"
        @click="openCreate"
      >
        <Plus :size="16" aria-hidden="true" />
        {{ createLabel() }}
      </button>
    </EmptyState>
    <div v-else-if="filtered.length === 0" class="catalog-no-results">
      <Search :size="21" aria-hidden="true" />
      <p>{{ $t("catalog.noResults") }}</p>
      <button class="button-link" type="button" @click="resetFilters">
        {{ $t("catalog.reset") }}
      </button>
    </div>
    <div v-else class="catalog-table-wrap">
      <table class="catalog-table venue-wallet-table">
        <thead>
          <tr>
            <SortableHeader
              :label="$t('catalog.asset.symbol')"
              :direction="activeDirection('symbol')"
              @sort="toggleSort('symbol')"
            />
            <th>{{ $t("catalog.asset.name") }}</th>
            <SortableHeader
              :label="$t('catalog.asset.type')"
              :direction="activeDirection('type')"
              @sort="toggleSort('type')"
            />
            <SortableHeader
              :label="$t('venues.status')"
              :direction="activeDirection('status')"
              @sort="toggleSort('status')"
            />
            <th v-if="auth.user?.is_staff" class="catalog-table__actions">
              <span class="sr-only">{{ $t("catalog.actions") }}</span>
            </th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="capability in filtered" :key="capability.id">
            <td :data-label="$t('catalog.asset.symbol')">
              <strong class="catalog-symbol">
                {{ capability.asset.symbol }}
              </strong>
            </td>
            <td :data-label="$t('catalog.asset.name')">
              {{ capability.asset.name ?? "—" }}
            </td>
            <td :data-label="$t('catalog.asset.type')">
              <span
                :class="[
                  'catalog-tag',
                  `catalog-tag--${capability.asset.asset_type}`,
                ]"
              >
                {{ $t(`catalog.types.${capability.asset.asset_type}`) }}
              </span>
            </td>
            <td :data-label="$t('venues.status')">
              <span
                :class="[
                  'catalog-tag',
                  capability.is_active
                    ? 'catalog-tag--active'
                    : 'catalog-tag--archived',
                ]"
              >
                {{
                  $t(
                    capability.is_active
                      ? "venues.active"
                      : "venues.archivedState",
                  )
                }}
              </span>
            </td>
            <td v-if="auth.user?.is_staff" class="catalog-row-actions">
              <button
                class="icon-action"
                type="button"
                :disabled="statusMutation.isPending.value"
                :aria-label="
                  $t(capability.is_active ? 'venues.archive' : 'venues.restore')
                "
                @click="statusMutation.mutate(capability)"
              >
                <Archive
                  v-if="capability.is_active"
                  :size="15"
                  aria-hidden="true"
                />
                <ArchiveRestore v-else :size="15" aria-hidden="true" />
              </button>
              <button
                v-if="!capability.is_active"
                class="icon-action icon-action--danger"
                type="button"
                :aria-label="$t('catalog.delete')"
                @click="deleteTarget = capability"
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
      :title="$t('venues.walletAssets.createTitle')"
      :description="$t('venues.walletAssets.formDescription')"
      :submit-label="$t('venues.walletAssets.create')"
      :cancel-label="$t('common.cancel')"
      :busy="createMutation.isPending.value"
      :invalid="assetId === null"
      @submit="createMutation.mutate()"
    >
      <label class="field">
        <span>{{ $t("catalog.asset.title") }}</span>
        <SearchableSelect
          v-model="assetId"
          :options="assetOptions"
          :placeholder="$t('venues.walletAssets.selectResource')"
          :empty-label="$t('venues.walletAssets.noResources')"
        />
      </label>
    </FormDialog>

    <ConfirmDialog
      :open="deleteTarget !== null"
      :title="$t('venues.walletAssets.deleteTitle')"
      :description="
        $t('venues.walletAssets.deleteBody', {
          symbol: deleteTarget?.asset.symbol,
        })
      "
      :confirm-label="$t('catalog.delete')"
      :cancel-label="$t('common.cancel')"
      :busy="removeMutation.isPending.value"
      @update:open="!$event && (deleteTarget = null)"
      @confirm="deleteTarget && removeMutation.mutate(deleteTarget)"
    />
  </section>
</template>

<script setup lang="ts">
import { ArrowLeftRight, Pencil, Plus, Search, Trash2 } from "@lucide/vue";
import { computed, reactive, ref } from "vue";
import { useMutation, useQuery, useQueryClient } from "@tanstack/vue-query";
import { useI18n } from "vue-i18n";
import { useRouter } from "vue-router";

import PaginationControls from "@/components/PaginationControls.vue";
import RemoteCatalogSelect from "@/components/RemoteCatalogSelect.vue";
import { usePagination } from "@/composables/usePagination";
import { ApiError } from "@/api/errors";
import ConfirmDialog from "@/components/ConfirmDialog.vue";
import EmptyState from "@/components/EmptyState.vue";
import ErrorState from "@/components/ErrorState.vue";
import FormDialog from "@/components/FormDialog.vue";
import LoadingState from "@/components/LoadingState.vue";
import SortableHeader from "@/components/SortableHeader.vue";
import {
  createPair,
  deletePair,
  listAssets,
  listPairs,
  updatePair,
  type Pair,
} from "@/features/catalog/api";
import {
  type PairSortKey,
  type SortDirection,
} from "@/features/catalog/filters";
import { useAuthStore } from "@/stores/auth";
import { useToastStore } from "@/stores/toasts";

const auth = useAuthStore();
const toasts = useToastStore();
const router = useRouter();
const queryClient = useQueryClient();
const { t } = useI18n();

const search = ref("");
const sortKey = ref<PairSortKey>("canonical_symbol");
const sortDirection = ref<SortDirection>("asc");
const dialogOpen = ref(false);
const editing = ref<Pair | null>(null);
const deleteTarget = ref<Pair | null>(null);
const form = reactive<{ base_id: number | null; quote_id: number | null }>({
  base_id: null,
  quote_id: null,
});

const assetsQuery = useQuery({
  queryKey: ["catalog", "assets"],
  queryFn: () => listAssets({ page_size: 1 }),
});
const criteria = computed(() => ({
  q: search.value,
  sort: sortKey.value,
  order: sortDirection.value,
}));
const pagination = usePagination(criteria);
const { page, pageSize } = pagination;
const pairsQuery = useQuery({
  queryKey: computed(() => [
    "catalog",
    "pairs",
    criteria.value,
    pagination.params.value,
  ]),
  queryFn: () => listPairs({ ...criteria.value, ...pagination.params.value }),
});
pagination.track(computed(() => pairsQuery.data.value));
const pairs = computed(() => pairsQuery.data.value?.items ?? []);
const filtered = pairs;
const canCreate = computed(() => (assetsQuery.data.value?.total ?? 0) >= 2);
const formInvalid = computed(
  () =>
    form.base_id === null ||
    form.quote_id === null ||
    form.base_id === form.quote_id,
);

function showError(error: unknown, context: "save" | "delete"): void {
  const apiError = error instanceof ApiError ? error : null;
  const description =
    apiError?.code === "pair_in_use"
      ? t("catalog.errors.pairInUse")
      : apiError?.code === "validation_error"
        ? t("catalog.errors.validation")
        : context === "save" && apiError?.code === "conflict"
          ? t("catalog.errors.pairConflict")
          : t("catalog.errors.unavailable");
  toasts.error({
    title: t(
      context === "save"
        ? "catalog.pair.saveFailed"
        : "catalog.pair.deleteFailed",
    ),
    description,
  });
}

const saveMutation = useMutation({
  mutationFn: () =>
    editing.value === null
      ? createPair({ base_id: form.base_id ?? 0, quote_id: form.quote_id ?? 0 })
      : updatePair(editing.value.id, {
          base_id: form.base_id ?? 0,
          quote_id: form.quote_id ?? 0,
        }),
  onSuccess: async () => {
    await queryClient.invalidateQueries({ queryKey: ["catalog"] });
    toasts.success({
      title: t(
        editing.value === null ? "catalog.pair.created" : "catalog.pair.saved",
      ),
    });
    dialogOpen.value = false;
  },
  onError: (error) => showError(error, "save"),
});

const removeMutation = useMutation({
  mutationFn: (pair: Pair) => deletePair(pair.id),
  onSuccess: async (_, pair) => {
    await queryClient.invalidateQueries({ queryKey: ["catalog"] });
    toasts.success({
      title: t("catalog.pair.deleted"),
      description: pair.canonical_symbol,
    });
    deleteTarget.value = null;
  },
  onError: (error) => showError(error, "delete"),
});

function openCreate(): void {
  if (!canCreate.value) {
    void router.push("/catalog/assets");
    return;
  }
  editing.value = null;
  Object.assign(form, { base_id: null, quote_id: null });
  dialogOpen.value = true;
}

function openEdit(pair: Pair): void {
  editing.value = pair;
  Object.assign(form, { base_id: pair.base.id, quote_id: pair.quote.id });
  dialogOpen.value = true;
}

async function retryQueries(): Promise<void> {
  await Promise.all([pairsQuery.refetch(), assetsQuery.refetch()]);
}

function toggleSort(key: PairSortKey): void {
  if (sortKey.value === key) {
    sortDirection.value = sortDirection.value === "asc" ? "desc" : "asc";
    return;
  }
  sortKey.value = key;
  sortDirection.value = "asc";
}

function activeDirection(key: PairSortKey): SortDirection | null {
  return sortKey.value === key ? sortDirection.value : null;
}
</script>

<template>
  <section class="catalog-section" aria-labelledby="pairs-title">
    <header class="catalog-section__header">
      <div>
        <h2 id="pairs-title" class="catalog-section__title">
          <ArrowLeftRight :size="21" aria-hidden="true" />
          {{ $t("catalog.pair.title") }}
        </h2>
        <p class="catalog-section__description">
          {{ $t("catalog.pair.description") }}
        </p>
      </div>
      <button
        v-if="auth.user?.is_staff"
        class="button button--primary"
        type="button"
        @click="openCreate"
      >
        <Plus :size="17" aria-hidden="true" />
        {{
          canCreate
            ? $t("catalog.pair.create")
            : $t("catalog.asset.addRequired")
        }}
      </button>
    </header>

    <div class="catalog-toolbar" role="search">
      <label class="search-field">
        <span class="sr-only">{{ $t("catalog.searchPairs") }}</span>
        <Search class="search-field__icon" :size="16" aria-hidden="true" />
        <input
          v-model="search"
          type="search"
          :placeholder="$t('catalog.searchPairs')"
        />
      </label>
      <button
        v-if="search"
        class="button-link"
        type="button"
        @click="search = ''"
      >
        {{ $t("catalog.reset") }}
      </button>
      <span class="catalog-toolbar__count">{{
        pairsQuery.data.value?.total ?? 0
      }}</span>
    </div>

    <LoadingState
      v-if="pairsQuery.isPending.value || assetsQuery.isPending.value"
      :label="$t('catalog.loadingPairs')"
    />
    <ErrorState
      v-else-if="pairsQuery.isError.value || assetsQuery.isError.value"
      :title="$t('catalog.loadFailed')"
      :description="$t('catalog.errors.unavailable')"
      @retry="retryQueries"
    />
    <EmptyState
      v-else-if="pairs.length === 0 && !search"
      :title="$t('catalog.pair.emptyTitle')"
    >
      <template #icon><ArrowLeftRight :size="24" /></template>
      <button
        v-if="auth.user?.is_staff"
        class="button button--primary"
        type="button"
        @click="openCreate"
      >
        <Plus :size="17" aria-hidden="true" />
        {{
          canCreate
            ? $t("catalog.pair.createFirst")
            : $t("catalog.asset.goToAssets")
        }}
      </button>
    </EmptyState>
    <div v-else-if="filtered.length === 0" class="catalog-no-results">
      <Search :size="22" aria-hidden="true" />
      <p>{{ $t("catalog.noResults") }}</p>
      <button class="button-link" type="button" @click="search = ''">
        {{ $t("catalog.reset") }}
      </button>
    </div>
    <div v-else class="catalog-table-wrap">
      <table class="catalog-table catalog-table--pairs">
        <thead>
          <tr>
            <SortableHeader
              :label="$t('catalog.pair.market')"
              :direction="activeDirection('canonical_symbol')"
              @sort="toggleSort('canonical_symbol')"
            />
            <SortableHeader
              :label="$t('catalog.pair.base')"
              :direction="activeDirection('base')"
              @sort="toggleSort('base')"
            />
            <SortableHeader
              :label="$t('catalog.pair.quote')"
              :direction="activeDirection('quote')"
              @sort="toggleSort('quote')"
            />
            <SortableHeader
              :label="$t('catalog.pair.typeRelation')"
              :direction="activeDirection('type_relation')"
              @sort="toggleSort('type_relation')"
            />
            <th v-if="auth.user?.is_staff" class="catalog-table__actions">
              <span class="sr-only">{{ $t("catalog.actions") }}</span>
            </th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="pair in filtered" :key="pair.id">
            <td :data-label="$t('catalog.pair.market')">
              <strong class="catalog-symbol">{{
                pair.canonical_symbol
              }}</strong>
            </td>
            <td :data-label="$t('catalog.pair.base')">
              <span class="asset-cell"
                ><strong>{{ pair.base.symbol }}</strong
                ><small>{{
                  pair.base.name || $t(`catalog.types.${pair.base.asset_type}`)
                }}</small></span
              >
            </td>
            <td :data-label="$t('catalog.pair.quote')">
              <span class="asset-cell"
                ><strong>{{ pair.quote.symbol }}</strong
                ><small>{{
                  pair.quote.name ||
                  $t(`catalog.types.${pair.quote.asset_type}`)
                }}</small></span
              >
            </td>
            <td :data-label="$t('catalog.pair.typeRelation')">
              <span class="pair-type-relation">
                <span
                  :class="[
                    'catalog-tag',
                    `catalog-tag--${pair.base.asset_type}`,
                  ]"
                >
                  {{ $t(`catalog.types.${pair.base.asset_type}`) }}
                </span>
                <span class="pair-type-relation__separator">/</span>
                <span
                  :class="[
                    'catalog-tag',
                    `catalog-tag--${pair.quote.asset_type}`,
                  ]"
                >
                  {{ $t(`catalog.types.${pair.quote.asset_type}`) }}
                </span>
              </span>
            </td>
            <td v-if="auth.user?.is_staff" class="catalog-row-actions">
              <button
                class="icon-action"
                type="button"
                :aria-label="$t('catalog.edit')"
                @click="openEdit(pair)"
              >
                <Pencil :size="15" aria-hidden="true" />
              </button>
              <button
                class="icon-action icon-action--danger"
                type="button"
                :aria-label="$t('catalog.delete')"
                @click="deleteTarget = pair"
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
        $t(editing ? 'catalog.pair.editTitle' : 'catalog.pair.createTitle')
      "
      :description="$t('catalog.pair.formDescription')"
      :submit-label="
        $t(editing ? 'catalog.saveChanges' : 'catalog.pair.create')
      "
      :cancel-label="$t('common.cancel')"
      :busy="saveMutation.isPending.value"
      :invalid="formInvalid"
      @submit="saveMutation.mutate()"
    >
      <label class="field">
        <span>{{ $t("catalog.pair.base") }}</span>
        <RemoteCatalogSelect
          v-model="form.base_id"
          resource="assets"
          :exclude-id="form.quote_id"
          :placeholder="$t('catalog.pair.selectBase')"
          :empty-label="$t('catalog.noOptions')"
        />
        <small>{{ $t("catalog.pair.baseHint") }}</small>
      </label>
      <label class="field">
        <span>{{ $t("catalog.pair.quote") }}</span>
        <RemoteCatalogSelect
          v-model="form.quote_id"
          resource="assets"
          :exclude-id="form.base_id"
          :placeholder="$t('catalog.pair.selectQuote')"
          :empty-label="$t('catalog.noOptions')"
          :disabled="form.base_id === null"
        />
        <small>{{
          form.base_id !== null
            ? $t("catalog.pair.quoteHint")
            : $t("catalog.pair.selectBaseFirst")
        }}</small>
      </label>
    </FormDialog>

    <ConfirmDialog
      :open="deleteTarget !== null"
      :title="$t('catalog.pair.deleteTitle')"
      :description="
        $t('catalog.pair.deleteBody', {
          symbol: deleteTarget?.canonical_symbol,
        })
      "
      :confirm-label="$t('catalog.delete')"
      :cancel-label="$t('common.cancel')"
      :busy="removeMutation.isPending.value"
      @update:open="!$event && (deleteTarget = null)"
      @confirm="deleteTarget && removeMutation.mutate(deleteTarget)"
    />
    <PaginationControls
      v-model:page="page"
      v-model:page-size="pageSize"
      :total="pairsQuery.data.value?.total ?? 0"
      :busy="pairsQuery.isFetching.value"
    />
  </section>
</template>

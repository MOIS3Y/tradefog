<script setup lang="ts">
import {
  Archive,
  ArchiveRestore,
  CandlestickChart,
  Pencil,
  Plus,
  Search,
  Trash2,
} from "@lucide/vue";
import { useMutation, useQuery, useQueryClient } from "@tanstack/vue-query";
import { computed, reactive, ref } from "vue";
import { useI18n } from "vue-i18n";
import { useRouter } from "vue-router";

import PaginationControls from "@/components/PaginationControls.vue";
import RemoteCatalogSelect from "@/components/RemoteCatalogSelect.vue";
import { usePagination } from "@/composables/usePagination";
import { ApiError } from "@/api/errors";
import AppSelect, { type SelectOption } from "@/components/AppSelect.vue";
import ConfirmDialog from "@/components/ConfirmDialog.vue";
import EmptyState from "@/components/EmptyState.vue";
import ErrorState from "@/components/ErrorState.vue";
import FormDialog from "@/components/FormDialog.vue";
import LoadingState from "@/components/LoadingState.vue";
import SortableHeader from "@/components/SortableHeader.vue";
import { listPairs } from "@/features/catalog/api";
import {
  createInstrument,
  deleteInstrument,
  listInstruments,
  updateInstrument,
  type Instrument,
  type ProductKind,
  type Venue,
} from "@/features/venues/api";
import {
  type InstrumentSortKey,
  type VisibilityFilter,
} from "@/features/venues/filters";
import { useAuthStore } from "@/stores/auth";
import { useToastStore } from "@/stores/toasts";
import { formatDecimal } from "@/utils/decimal";
import type { SortDirection } from "@/utils/sorting";

interface InstrumentForm {
  pair_id: number | null;
  product: ProductKind;
  exec_symbol: string;
  price_step: string;
  qty_step: string;
  min_qty: string;
  min_notional: string;
  settlement_asset_id: number;
}

const props = defineProps<{ venue: Venue }>();
const auth = useAuthStore();
const toasts = useToastStore();
const router = useRouter();
const queryClient = useQueryClient();
const { t } = useI18n();

const search = ref("");
const visibility = ref<VisibilityFilter>("active");
const sortKey = ref<InstrumentSortKey>("exec_symbol");
const sortDirection = ref<SortDirection>("asc");
const dialogOpen = ref(false);
const editing = ref<Instrument | null>(null);
const deleteTarget = ref<Instrument | null>(null);
const form = reactive<InstrumentForm>({
  pair_id: null,
  product: "spot",
  exec_symbol: "",
  price_step: "",
  qty_step: "",
  min_qty: "",
  min_notional: "",
  settlement_asset_id: 0,
});

const queryKey = computed(() => [
  "catalog",
  "venues",
  props.venue.id,
  "instruments",
]);
const criteria = computed(() => ({
  venue: props.venue.id,
  q: search.value,
  visibility: visibility.value,
  sort: sortKey.value,
  order: sortDirection.value,
}));
const pagination = usePagination(criteria);
const { page, pageSize } = pagination;
const query = useQuery({
  queryKey: computed(() => [
    ...queryKey.value,
    criteria.value,
    pagination.params.value,
  ]),
  queryFn: () =>
    listInstruments(props.venue.id, {
      ...criteria.value,
      ...pagination.params.value,
    }),
});
pagination.track(computed(() => query.data.value));
const pairsQuery = useQuery({
  queryKey: ["catalog", "pairs"],
  queryFn: () => listPairs({ page_size: 1 }),
});

const instruments = computed(() => query.data.value?.items ?? []);
const pairs = computed(() => pairsQuery.data.value?.items ?? []);
const filtered = instruments;
const formInvalid = computed(
  () =>
    form.pair_id === null ||
    form.exec_symbol.trim().length === 0 ||
    !isPositiveDecimal(form.price_step) ||
    !isPositiveDecimal(form.qty_step) ||
    !isOptionalPositiveDecimal(form.min_qty) ||
    !isOptionalPositiveDecimal(form.min_notional),
);
const visibilityOptions = computed<SelectOption<VisibilityFilter>[]>(() => [
  { value: "active", label: t("venues.visibility.active") },
  { value: "archived", label: t("venues.visibility.archived") },
  { value: "all", label: t("venues.visibility.all") },
]);
const productOptions = computed<SelectOption<ProductKind>[]>(() => [
  { value: "spot", label: t("venues.products.spot") },
  {
    value: "perpetual_future",
    label: t("venues.products.perpetual_future"),
  },
  { value: "cash_equity", label: t("venues.products.cash_equity") },
]);
function isPositiveDecimal(value: string): boolean {
  const parsed = Number(value);
  return value.trim().length > 0 && Number.isFinite(parsed) && parsed > 0;
}

function isOptionalPositiveDecimal(value: string): boolean {
  return value.trim().length === 0 || isPositiveDecimal(value);
}

function optionalDecimal(value: string): string | null {
  return value.trim().length === 0 ? null : value.trim();
}

function showError(error: unknown, action: "save" | "delete"): void {
  const apiError = error instanceof ApiError ? error : null;
  const description =
    apiError?.code === "instrument_in_use"
      ? t("venues.instruments.errors.inUse")
      : apiError?.code === "instrument_not_archived"
        ? t("venues.instruments.errors.notArchived")
        : apiError?.code === "validation_error"
          ? t("catalog.errors.validation")
          : apiError?.code === "conflict"
            ? t("venues.instruments.errors.conflict")
            : t("catalog.errors.unavailable");
  toasts.error({
    title: t(
      action === "save"
        ? "venues.instruments.saveFailed"
        : "venues.instruments.deleteFailed",
    ),
    description,
  });
}

const saveMutation = useMutation({
  mutationFn: () => {
    const input = {
      product: form.product,
      exec_symbol: form.exec_symbol,
      price_step: form.price_step,
      qty_step: form.qty_step,
      min_qty: optionalDecimal(form.min_qty),
      min_notional: optionalDecimal(form.min_notional),
      settlement_asset_id: form.settlement_asset_id || null,
    };
    if (editing.value !== null) {
      return updateInstrument(editing.value.id, input);
    }
    return createInstrument(props.venue.id, {
      ...input,
      pair_id: form.pair_id ?? 0,
      is_active: true,
    });
  },
  onSuccess: async (instrument) => {
    await queryClient.invalidateQueries({ queryKey: ["catalog"] });
    toasts.success({
      title: t(
        editing.value === null
          ? "venues.instruments.created"
          : "venues.instruments.saved",
      ),
    });
    dialogOpen.value = false;
  },
  onError: (error) => showError(error, "save"),
});

const statusMutation = useMutation({
  mutationFn: (instrument: Instrument) =>
    updateInstrument(instrument.id, { is_active: !instrument.is_active }),
  onSuccess: async (instrument) => {
    await queryClient.invalidateQueries({ queryKey: ["catalog"] });
    toasts.success({
      title: t(
        instrument.is_active
          ? "venues.instruments.restored"
          : "venues.instruments.archived",
      ),
      description: instrument.exec_symbol,
    });
  },
  onError: (error) => showError(error, "save"),
});

const removeMutation = useMutation({
  mutationFn: (instrument: Instrument) => deleteInstrument(instrument.id),
  onSuccess: async (_, instrument) => {
    await queryClient.invalidateQueries({ queryKey: ["catalog"] });
    toasts.success({
      title: t("venues.instruments.deleted"),
      description: instrument.exec_symbol,
    });
    deleteTarget.value = null;
  },
  onError: (error) => showError(error, "delete"),
});

function openCreate(): void {
  if (pairs.value.length === 0) {
    void router.push("/catalog/pairs");
    return;
  }
  editing.value = null;
  Object.assign(form, {
    pair_id: null,
    product: "spot",
    exec_symbol: "",
    price_step: "",
    qty_step: "",
    min_qty: "",
    min_notional: "",
    settlement_asset_id: 0,
  });
  dialogOpen.value = true;
}

function openEdit(instrument: Instrument): void {
  editing.value = instrument;
  Object.assign(form, {
    pair_id: instrument.pair.id,
    product: instrument.product,
    exec_symbol: instrument.exec_symbol,
    price_step: instrument.price_step,
    qty_step: instrument.qty_step,
    min_qty: instrument.min_qty ?? "",
    min_notional: instrument.min_notional ?? "",
    settlement_asset_id: instrument.settlement_asset?.id ?? 0,
  });
  dialogOpen.value = true;
}

function resetFilters(): void {
  search.value = "";
  visibility.value = "active";
}

async function retryQueries(): Promise<void> {
  await Promise.all([query.refetch(), pairsQuery.refetch()]);
}

function toggleSort(key: InstrumentSortKey): void {
  if (sortKey.value === key) {
    sortDirection.value = sortDirection.value === "asc" ? "desc" : "asc";
    return;
  }
  sortKey.value = key;
  sortDirection.value = "asc";
}

function activeDirection(key: InstrumentSortKey): SortDirection | null {
  return sortKey.value === key ? sortDirection.value : null;
}
</script>

<template>
  <section class="venue-subsection" aria-labelledby="instruments-title">
    <header class="venue-subsection__header">
      <div>
        <h4 id="instruments-title">
          <CandlestickChart :size="18" aria-hidden="true" />
          {{ $t("venues.instruments.title") }}
        </h4>
        <p>{{ $t("venues.instruments.description") }}</p>
      </div>
      <button
        v-if="auth.user?.is_staff"
        class="button button--secondary"
        type="button"
        @click="openCreate"
      >
        <Plus :size="16" aria-hidden="true" />
        {{
          $t(
            pairs.length
              ? "venues.instruments.create"
              : "venues.instruments.addPair",
          )
        }}
      </button>
    </header>

    <div class="venue-subsection__toolbar" role="search">
      <label class="search-field">
        <span class="sr-only">{{ $t("venues.instruments.search") }}</span>
        <Search class="search-field__icon" :size="16" aria-hidden="true" />
        <input
          v-model="search"
          type="search"
          :placeholder="$t('venues.instruments.search')"
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
        {{ query.data.value?.total ?? 0 }}
      </span>
    </div>

    <LoadingState
      v-if="query.isPending.value || pairsQuery.isPending.value"
      :label="$t('venues.instruments.loading')"
    />
    <ErrorState
      v-else-if="query.isError.value || pairsQuery.isError.value"
      :title="$t('venues.instruments.loadFailed')"
      :description="$t('catalog.errors.unavailable')"
      @retry="retryQueries"
    />
    <EmptyState
      v-else-if="instruments.length === 0 && !search && visibility === 'active'"
      :title="$t('venues.instruments.emptyTitle')"
    >
      <template #icon><CandlestickChart :size="23" /></template>
      <button
        v-if="auth.user?.is_staff"
        class="button button--secondary"
        type="button"
        @click="openCreate"
      >
        <Plus :size="16" aria-hidden="true" />
        {{
          $t(
            pairs.length
              ? "venues.instruments.createFirst"
              : "venues.instruments.addPair",
          )
        }}
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
      <table class="catalog-table venue-instrument-table">
        <thead>
          <tr>
            <SortableHeader
              :label="$t('venues.instruments.execSymbol')"
              :direction="activeDirection('exec_symbol')"
              @sort="toggleSort('exec_symbol')"
            />
            <SortableHeader
              :label="$t('catalog.pair.market')"
              :direction="activeDirection('pair')"
              @sort="toggleSort('pair')"
            />
            <SortableHeader
              :label="$t('venues.instruments.product')"
              :direction="activeDirection('product')"
              @sort="toggleSort('product')"
            />
            <SortableHeader
              :label="$t('venues.instruments.settlement')"
              :direction="activeDirection('settlement')"
              @sort="toggleSort('settlement')"
            />
            <th>{{ $t("venues.instruments.rules") }}</th>
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
          <tr v-for="instrument in filtered" :key="instrument.id">
            <td :data-label="$t('venues.instruments.execSymbol')">
              <strong class="catalog-symbol">{{
                instrument.exec_symbol
              }}</strong>
            </td>
            <td :data-label="$t('catalog.pair.market')">
              <span class="venue-instrument-market">
                {{ instrument.pair.canonical_symbol }}
              </span>
            </td>
            <td :data-label="$t('venues.instruments.product')">
              <span class="product-badge">
                {{ $t(`venues.products.${instrument.product}`) }}
              </span>
            </td>
            <td :data-label="$t('venues.instruments.settlement')">
              {{ instrument.settlement_asset?.symbol ?? "—" }}
            </td>
            <td :data-label="$t('venues.instruments.rules')">
              <span class="instrument-rules">
                <small>
                  {{ $t("venues.instruments.priceStep") }}
                  <strong>{{ formatDecimal(instrument.price_step) }}</strong>
                </small>
                <small>
                  {{ $t("venues.instruments.qtyStep") }}
                  <strong>{{ formatDecimal(instrument.qty_step) }}</strong>
                </small>
                <small v-if="instrument.min_qty">
                  {{ $t("venues.instruments.minQty") }}
                  <strong>{{ formatDecimal(instrument.min_qty) }}</strong>
                </small>
                <small v-if="instrument.min_notional">
                  {{ $t("venues.instruments.minNotional") }}
                  <strong>{{ formatDecimal(instrument.min_notional) }}</strong>
                </small>
              </span>
            </td>
            <td :data-label="$t('venues.status')">
              <span
                :class="[
                  'catalog-tag',
                  instrument.is_active
                    ? 'catalog-tag--active'
                    : 'catalog-tag--archived',
                ]"
              >
                {{
                  $t(
                    instrument.is_active
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
                :aria-label="$t('catalog.edit')"
                @click="openEdit(instrument)"
              >
                <Pencil :size="15" aria-hidden="true" />
              </button>
              <button
                class="icon-action"
                type="button"
                :disabled="statusMutation.isPending.value"
                :aria-label="
                  $t(instrument.is_active ? 'venues.archive' : 'venues.restore')
                "
                @click="statusMutation.mutate(instrument)"
              >
                <Archive
                  v-if="instrument.is_active"
                  :size="15"
                  aria-hidden="true"
                />
                <ArchiveRestore v-else :size="15" aria-hidden="true" />
              </button>
              <button
                v-if="!instrument.is_active"
                class="icon-action icon-action--danger"
                type="button"
                :aria-label="$t('catalog.delete')"
                @click="deleteTarget = instrument"
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
        $t(
          editing
            ? 'venues.instruments.editTitle'
            : 'venues.instruments.createTitle',
        )
      "
      :description="$t('venues.instruments.formDescription')"
      :submit-label="
        $t(editing ? 'catalog.saveChanges' : 'venues.instruments.create')
      "
      :cancel-label="$t('common.cancel')"
      :busy="saveMutation.isPending.value"
      :invalid="formInvalid"
      @submit="saveMutation.mutate()"
    >
      <label class="field">
        <span>{{ $t("catalog.pair.title") }}</span>
        <RemoteCatalogSelect
          v-model="form.pair_id"
          resource="pairs"
          :placeholder="$t('venues.instruments.selectPair')"
          :empty-label="$t('venues.instruments.noPairs')"
          :disabled="editing !== null"
        />
        <small v-if="editing">{{ $t("venues.instruments.pairLocked") }}</small>
      </label>
      <label class="field">
        <span>{{ $t("venues.instruments.product") }}</span>
        <AppSelect
          v-model="form.product"
          :options="productOptions"
          :label="$t('venues.instruments.product')"
        />
      </label>
      <label class="field">
        <span>{{ $t("venues.instruments.execSymbol") }}</span>
        <input
          v-model="form.exec_symbol"
          maxlength="64"
          autocomplete="off"
          placeholder="BTCUSDT"
          required
        />
      </label>
      <div class="form-grid form-grid--two">
        <label class="field">
          <span>{{ $t("venues.instruments.priceStep") }}</span>
          <input
            v-model="form.price_step"
            inputmode="decimal"
            autocomplete="off"
            placeholder="0.01"
            required
          />
        </label>
        <label class="field">
          <span>{{ $t("venues.instruments.qtyStep") }}</span>
          <input
            v-model="form.qty_step"
            inputmode="decimal"
            autocomplete="off"
            placeholder="0.001"
            required
          />
        </label>
        <label class="field">
          <span>{{ $t("venues.instruments.minQty") }}</span>
          <input
            v-model="form.min_qty"
            inputmode="decimal"
            autocomplete="off"
            placeholder="0.001"
          />
        </label>
        <label class="field">
          <span>{{ $t("venues.instruments.minNotional") }}</span>
          <input
            v-model="form.min_notional"
            inputmode="decimal"
            autocomplete="off"
            placeholder="10"
          />
        </label>
      </div>
      <label class="field">
        <span>{{ $t("venues.instruments.settlement") }}</span>
        <RemoteCatalogSelect
          v-model="form.settlement_asset_id"
          resource="assets"
          :extra-options="[
            { value: 0, label: $t('venues.instruments.noSettlement') },
          ]"
          :placeholder="$t('venues.instruments.selectSettlement')"
          :empty-label="$t('catalog.noOptions')"
        />
        <small>{{ $t("venues.instruments.settlementHint") }}</small>
      </label>
    </FormDialog>

    <ConfirmDialog
      :open="deleteTarget !== null"
      :title="$t('venues.instruments.deleteTitle')"
      :description="
        $t('venues.instruments.deleteBody', {
          symbol: deleteTarget?.exec_symbol,
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
      :total="query.data.value?.total ?? 0"
      :busy="query.isFetching.value"
    />
  </section>
</template>

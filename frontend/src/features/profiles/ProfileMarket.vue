<script setup lang="ts">
import { useDialogLeaveGuard } from "@/composables/useLeaveGuard";
/** Profile-local market setup: selected imports or manual specifications. */
import { computed, reactive, ref, watch } from "vue";
import { useMutation, useQuery, useQueryClient } from "@tanstack/vue-query";
import { useI18n } from "vue-i18n";
import {
  Archive,
  ArchiveRestore,
  Pencil,
  Plus,
  RefreshCw,
  Search,
  Trash2,
} from "@lucide/vue";
import AppSelect from "@/components/AppSelect.vue";
import AssetSymbolInput from "./AssetSymbolInput.vue";
import FormDialog from "@/components/FormDialog.vue";
import ConfirmDialog from "@/components/ConfirmDialog.vue";
import PaginationControls from "@/components/PaginationControls.vue";
import SortableHeader from "@/components/SortableHeader.vue";
import ErrorState from "@/components/ErrorState.vue";
import LoadingState from "@/components/LoadingState.vue";
import EmptyState from "@/components/EmptyState.vue";
import { usePagination } from "@/composables/usePagination";
import type { Profile } from "./api";
import {
  getAsset,
  listInstruments,
  createInstrument,
  updateInstrument,
  deleteInstrument,
  refreshInstrument,
  searchExchange,
  type Asset,
  type Instrument,
  type InstrumentSpec,
} from "./marketApi";
import { useToastStore } from "@/stores/toasts";
import { formatDecimal, isPositiveDecimal } from "@/utils/decimal";

const props = defineProps<{ profile: Profile }>();
const emit = defineEmits<{ fund: [assetId: number] }>();
const fundedAsset = ref<number | null>(null);
const { t } = useI18n();
const client = useQueryClient();
const toasts = useToastStore();
const manual = computed(() => props.profile.venue_type === "manual");
const search = ref("");
const visibility = ref<"all" | "active" | "archived">("active");
const order = ref<"asc" | "desc">("asc");
const productFilter = ref<Instrument["product"] | "all">("all");
const sortKey = ref<"symbol" | "product">("symbol");
function sortBy(key: "symbol" | "product"): void {
  order.value = sortKey.value === key && order.value === "asc" ? "desc" : "asc";
  sortKey.value = key;
}
const marketOptions = computed(() => [
  { value: "all", label: t("profileMarket.allMarkets") },
  ...products.value,
]);
const criteria = computed(() => ({
  product: productFilter.value === "all" ? undefined : productFilter.value,
  sort: sortKey.value,
  q: search.value,
  visibility: visibility.value,
  order: order.value,
}));
const pagination = usePagination(criteria);
const { page, pageSize } = pagination;
const query = useQuery({
  queryKey: computed(() => [
    "profile-market",
    props.profile.id,
    criteria.value,
    pagination.params.value,
  ]),
  queryFn: () =>
    listInstruments(props.profile.id, {
      ...pagination.params.value,
      ...criteria.value,
    }),
});
pagination.track(computed(() => query.data.value));
const items = computed(() => query.data.value?.items ?? []);
const dialog = ref(false);
const editing = ref<Instrument | null>(null);
const deleting = ref<Instrument | null>(null);
const form = reactive({
  symbol: "",
  product: "spot" as Instrument["product"],
  base: "",
  quote: "",
  baseType: undefined as Asset["asset_type"] | undefined,
  quoteType: undefined as Asset["asset_type"] | undefined,
  price_step: "0.01",
  qty_step: "0.001",
  min_qty: "",
  min_notional: "",
});
const products = computed(() =>
  (manual.value
    ? ["spot", "perpetual_future", "cash_equity"]
    : ["spot", "perpetual_future"]
  ).map((value) => ({
    value: value as Instrument["product"],
    label: t(`venues.products.${value}`),
  })),
);
const visibilityOptions = computed(() =>
  ["active", "archived", "all"].map((value) => ({
    value: value as typeof visibility.value,
    label: t(`profiles.visibility.${value}`),
  })),
);
const importSymbol = ref("");
const cursor = ref<string>();
const selectedSpec = ref<InstrumentSpec>();
const importQuery = useQuery({
  queryKey: computed(() => [
    "exchange-instruments",
    props.profile.venue_type,
    form.product,
    importSymbol.value,
    cursor.value,
  ]),
  enabled: computed(() => dialog.value && !manual.value && !editing.value),
  retry: false,
  queryFn: () =>
    searchExchange(
      props.profile.venue_type,
      form.product === "spot" ? "spot" : "perpetual_future",
      importSymbol.value,
      cursor.value,
    ),
});
watch(
  () => form.product,
  () => {
    cursor.value = undefined;
    selectedSpec.value = undefined;
  },
);
const invalid = computed(() => {
  if (!manual.value) return !editing.value && !selectedSpec.value;
  return (
    !form.base ||
    !form.quote ||
    form.base === form.quote ||
    !isPositiveDecimal(form.price_step) ||
    !isPositiveDecimal(form.qty_step) ||
    !![form.min_qty, form.min_notional].find(
      (value) => value && !isPositiveDecimal(value),
    )
  );
});
function label(item: Instrument): string {
  return item.exec_symbol.replace("/", " / ");
}
function archived(item: Instrument): boolean {
  return item.is_archived;
}
async function open(item: Instrument | null = null): Promise<void> {
  editing.value = item;
  selectedSpec.value = undefined;
  importSymbol.value = "";
  cursor.value = undefined;
  Object.assign(form, {
    symbol: item ? label(item) : "",
    product: item && "product" in item ? item.product : "spot",
    base: "",
    quote: "",
    baseType: undefined,
    quoteType: undefined,
    price_step: formatDecimal(item?.price_step ?? "0.01"),
    qty_step: formatDecimal(item?.qty_step ?? "0.001"),
    min_qty: formatDecimal(item?.min_qty ?? ""),
    min_notional: formatDecimal(item?.min_notional ?? ""),
  });
  if (item && manual.value) {
    try {
      const [base, quote] = await Promise.all([
        getAsset(props.profile.id, item.base_asset_id),
        getAsset(props.profile.id, item.quote_asset_id),
      ]);
      form.base = base.symbol;
      form.quote = quote.symbol;
    } catch (error) {
      failed(error as Error);
      return;
    }
  }
  dialog.value = true;
}
async function refresh(): Promise<void> {
  await client.invalidateQueries({
    queryKey: ["profile-market", props.profile.id],
  });
  await client.invalidateQueries({ queryKey: ["profiles", props.profile.id] });
}
function failed(error: Error): void {
  toasts.error({
    title: t("profileMarket.failed"),
    description: error.message,
  });
}
const save = useMutation({
  mutationFn: async () => {
    const rules = {
      price_step: form.price_step,
      qty_step: form.qty_step,
      min_qty: form.min_qty || null,
      min_notional: form.min_notional || null,
    };
    if (editing.value)
      return updateInstrument(props.profile.id, editing.value.id, {
        ...(manual.value ? rules : {}),
      });
    if (!manual.value) {
      if (!selectedSpec.value) throw new Error(t("profileMarket.choose"));
      return createInstrument(props.profile.id, {
        mode: "bybit",
        exec_symbol: selectedSpec.value.symbol,
        product: selectedSpec.value.product,
      });
    }
    return createInstrument(props.profile.id, {
      mode: "manual",
      product: form.product,
      base: { symbol: form.base, asset_type: form.baseType },
      quote: { symbol: form.quote, asset_type: form.quoteType },
      ...rules,
    });
  },
  onSuccess: async (item) => {
    fundedAsset.value = item.settlement_asset_id;
    await refresh();
    dialog.value = false;
    toasts.success({ title: t("profileMarket.saved") });
  },
  onError: failed,
});
const action = useMutation({
  mutationFn: async ({
    item,
    kind,
  }: {
    item: Instrument;
    kind: "archive" | "delete" | "refresh";
  }) => {
    if (kind === "refresh") return refreshInstrument(props.profile.id, item.id);
    if (kind === "delete") return deleteInstrument(props.profile.id, item.id);
    return updateInstrument(props.profile.id, item.id, {
      is_archived: !item.is_archived,
    });
  },
  onSuccess: async () => {
    await refresh();
    deleting.value = null;
  },
  onError: failed,
});
useDialogLeaveGuard(dialog, () => form);
</script>

<template>
  <section class="profile-panel profile-market">
    <header class="profile-panel__header">
      <div>
        <h4>{{ $t("profileMarket.title") }}</h4>
        <p>
          {{
            $t(manual ? "profileMarket.manualHelp" : "profileMarket.bybitHelp")
          }}
        </p>
      </div>
      <button
        v-if="!profile.is_archived"
        class="button button--primary"
        type="button"
        @click="open()"
      >
        <Plus :size="16" />{{
          $t(manual ? "profileMarket.addInstrument" : "profileMarket.import")
        }}
      </button>
    </header>
    <div v-if="fundedAsset" class="profile-toolbar">
      <p>{{ $t("profileMarket.fundingHint") }}</p>
      <button
        class="button button--secondary"
        @click="emit('fund', fundedAsset)"
      >
        {{ $t("profileMarket.fund") }}
      </button>
    </div>
    <div class="profile-toolbar">
      <label class="search-field"
        ><span class="sr-only">{{ $t("profileMarket.search") }}</span>
        <Search class="search-field__icon" :size="16" aria-hidden="true" />
        <input
          v-model="search"
          type="search"
          :placeholder="$t('profileMarket.search')"
      /></label>
      <AppSelect
        v-model="visibility"
        :options="visibilityOptions"
        :label="$t('profiles.status')"
      />
      <AppSelect
        v-model="productFilter"
        :options="marketOptions"
        :label="$t('profileMarket.product')"
      />
    </div>
    <LoadingState v-if="query.isPending.value" />
    <ErrorState v-else-if="query.isError.value" @retry="query.refetch()" />
    <EmptyState
      v-else-if="!items.length"
      :title="$t('profileMarket.empty')"
      :description="
        $t(manual ? 'profileMarket.manualHelp' : 'profileMarket.bybitHelp')
      "
    />
    <div v-else class="table-scroll">
      <table class="catalog-table">
        <thead>
          <tr>
            <SortableHeader
              :label="$t('profileMarket.symbol')"
              :direction="sortKey === 'symbol' ? order : null"
              @sort="sortBy('symbol')"
            />
            <th>{{ $t("profileMarket.assetTypes") }}</th>
            <SortableHeader
              :label="$t('profileMarket.product')"
              :direction="sortKey === 'product' ? order : null"
              @sort="sortBy('product')"
            />
            <th>{{ $t("profileMarket.priceStep") }}</th>
            <th>{{ $t("profileMarket.qtyStep") }}</th>
            <th>{{ $t("profiles.status") }}</th>
            <th>
              <span class="sr-only">{{ $t("catalog.edit") }}</span>
            </th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="item in items" :key="item.id">
            <td :data-label="$t('profileMarket.symbol')">
              <strong>{{ label(item) }}</strong>
            </td>
            <td
              :data-label="$t('profileMarket.assetTypes')"
              class="asset-type-pair"
            >
              <span
                class="catalog-tag"
                :class="`catalog-tag--${item.base_asset_type}`"
                >{{ $t(`catalog.types.${item.base_asset_type}`) }}</span
              >
              <span class="asset-type-pair__separator">/</span>
              <span
                class="catalog-tag"
                :class="`catalog-tag--${item.quote_asset_type}`"
                >{{ $t(`catalog.types.${item.quote_asset_type}`) }}</span
              >
            </td>
            <td :data-label="$t('profileMarket.product')">
              {{ $t(`venues.products.${item.product}`) }}
            </td>
            <td
              :data-label="$t('profileMarket.priceStep')"
              class="numeric-cell"
            >
              {{ formatDecimal(item.price_step) }}
            </td>
            <td :data-label="$t('profileMarket.qtyStep')" class="numeric-cell">
              {{ formatDecimal(item.qty_step) }}
            </td>
            <td :data-label="$t('profiles.status')">
              <span
                class="catalog-tag"
                :class="
                  archived(item) || !item.is_active
                    ? 'catalog-tag--archived'
                    : 'catalog-tag--active'
                "
                >{{
                  $t(
                    archived(item)
                      ? "profiles.archivedState"
                      : item.is_active
                        ? "profiles.active"
                        : "profileMarket.unavailable",
                  )
                }}</span
              >
            </td>
            <td class="table-actions">
              <button
                v-if="!manual && 'product' in item && !profile.is_archived"
                class="icon-action"
                :aria-label="$t('profileMarket.refresh')"
                :disabled="action.isPending.value"
                @click="action.mutate({ item, kind: 'refresh' })"
              >
                <RefreshCw :size="15" />
              </button>
              <button
                class="icon-action"
                v-if="manual"
                :aria-label="$t('catalog.edit')"
                :disabled="profile.is_archived"
                @click="open(item)"
              >
                <Pencil :size="15" />
              </button>
              <button
                class="icon-action"
                :aria-label="
                  $t(archived(item) ? 'profiles.restore' : 'profiles.archive')
                "
                :disabled="profile.is_archived || action.isPending.value"
                @click="action.mutate({ item, kind: 'archive' })"
              >
                <ArchiveRestore v-if="archived(item)" :size="15" /><Archive
                  v-else
                  :size="15"
                />
              </button>
              <button
                v-if="archived(item)"
                class="icon-action icon-action--danger"
                :aria-label="$t('catalog.delete')"
                @click="deleting = item"
              >
                <Trash2 :size="15" />
              </button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
    <PaginationControls
      v-model:page="page"
      v-model:page-size="pageSize"
      :total="query.data.value?.total ?? 0"
      :busy="query.isFetching.value"
    />
    <FormDialog
      v-model:open="dialog"
      :description="
        $t(manual ? 'profileMarket.manualHelp' : 'profileMarket.bybitHelp')
      "
      :title="
        $t(
          editing
            ? 'catalog.edit'
            : manual
              ? 'profileMarket.addInstrument'
              : 'profileMarket.import',
        )
      "
      :submit-label="
        $t(!manual && !editing ? 'profileMarket.import' : 'catalog.saveChanges')
      "
      :cancel-label="$t('common.cancel')"
      :busy="save.isPending.value"
      :invalid="invalid"
      @submit="save.mutate()"
    >
      <label class="field"
        ><span>{{ $t("profileMarket.product") }}</span>
        <AppSelect
          v-model="form.product"
          :options="products"
          :disabled="!!editing"
          :label="$t('profileMarket.product')"
      /></label>
      <template v-if="!manual && !editing">
        <label class="field"
          ><span>{{ $t("profileMarket.exactSymbol") }}</span
          ><input
            v-model="form.symbol"
            placeholder="BTCUSDT"
            @keydown.enter.prevent="
              importSymbol = form.symbol.trim().toUpperCase();
              cursor = undefined;
              selectedSpec = undefined;
            "
        /></label>
        <button
          class="button button--secondary"
          type="button"
          @click="
            importSymbol = form.symbol.trim().toUpperCase();
            cursor = undefined;
            selectedSpec = undefined;
          "
        >
          {{ $t("profileMarket.find") }}
        </button>
        <LoadingState v-if="importQuery.isPending.value" />
        <ErrorState
          v-else-if="importQuery.isError.value"
          @retry="importQuery.refetch()"
        />
        <div v-else class="profile-market__imports">
          <p v-if="!importQuery.data.value?.items.length">
            {{ $t("catalog.noResults") }}
          </p>
          <label
            v-for="spec in importQuery.data.value?.items"
            :key="spec.symbol"
            class="profile-market__import"
          >
            <input
              type="radio"
              name="import-symbol"
              :checked="selectedSpec?.symbol === spec.symbol"
              :disabled="!spec.is_active"
              @change="selectedSpec = spec"
            />
            <span
              ><strong>{{ spec.symbol }}</strong
              ><small
                >{{ spec.base }}/{{ spec.quote }} ·
                {{ formatDecimal(spec.price_step) }}</small
              ></span
            >
          </label>
          <button
            v-if="importQuery.data.value?.next_cursor"
            class="button button--secondary"
            type="button"
            @click="
              cursor = importQuery.data.value.next_cursor;
              selectedSpec = undefined;
            "
          >
            {{ $t("profileMarket.next") }}
          </button>
        </div>
      </template>
      <template v-if="manual">
        <AssetSymbolInput
          v-model="form.base"
          v-model:asset-type="form.baseType"
          :profile-id="profile.id"
          :label="$t('profileMarket.base')"
          :disabled="!!editing"
        />
        <AssetSymbolInput
          v-model="form.quote"
          v-model:asset-type="form.quoteType"
          :profile-id="profile.id"
          :label="$t('profileMarket.quote')"
          :disabled="!!editing"
        />
        <label
          v-for="field in [
            'price_step',
            'qty_step',
            'min_qty',
            'min_notional',
          ] as const"
          :key="field"
          class="field"
          ><span>{{ $t(`profileMarket.${field}`) }}</span
          ><input v-model="form[field]" inputmode="decimal"
        /></label>
      </template>
    </FormDialog>
    <ConfirmDialog
      :open="!!deleting"
      :title="$t('catalog.delete')"
      :description="$t('profileMarket.deleteHelp')"
      :confirm-label="$t('catalog.delete')"
      :cancel-label="$t('common.cancel')"
      :busy="action.isPending.value"
      @update:open="!$event && (deleting = null)"
      @confirm="deleting && action.mutate({ item: deleting, kind: 'delete' })"
    />
  </section>
</template>

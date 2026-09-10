<script setup lang="ts">
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
import RemoteCatalogSelect from "@/components/RemoteCatalogSelect.vue";
import FormDialog from "@/components/FormDialog.vue";
import ConfirmDialog from "@/components/ConfirmDialog.vue";
import PaginationControls from "@/components/PaginationControls.vue";
import SortableHeader from "@/components/SortableHeader.vue";
import ErrorState from "@/components/ErrorState.vue";
import LoadingState from "@/components/LoadingState.vue";
import EmptyState from "@/components/EmptyState.vue";
import { usePagination } from "@/composables/usePagination";
import type { Profile } from "./api";
import type { Page } from "@/api/pagination";
import {
  listAssets,
  listInstruments,
  createAsset,
  updateAsset,
  deleteAsset,
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
const { t } = useI18n();
const client = useQueryClient();
const toasts = useToastStore();
const manual = computed(() => props.profile.venue_type === "manual");
const tab = ref<"assets" | "instruments">("instruments");
const search = ref("");
const visibility = ref<"all" | "active" | "archived">("active");
const order = ref<"asc" | "desc">("asc");
const criteria = computed(() => ({
  tab: tab.value,
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
  queryFn: async (): Promise<Page<Asset | Instrument>> =>
    tab.value === "assets"
      ? listAssets(props.profile.id, {
          ...pagination.params.value,
          q: search.value,
          visibility: visibility.value,
          sort: "symbol",
          order: order.value,
        })
      : listInstruments(props.profile.id, {
          ...pagination.params.value,
          q: search.value,
          visibility: visibility.value,
          sort: "symbol",
          order: order.value,
        }),
});
pagination.track(computed(() => query.data.value));
const items = computed(() => query.data.value?.items ?? []);
const dialog = ref(false);
const editing = ref<Asset | Instrument | null>(null);
const deleting = ref<Asset | Instrument | null>(null);
const form = reactive({
  symbol: "",
  name: "",
  asset_type: "crypto" as Asset["asset_type"],
  product: "spot" as Instrument["product"],
  base: null as number | null,
  quote: null as number | null,
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
const types = computed(() =>
  ["crypto", "fiat", "equity"].map((value) => ({
    value: value as Asset["asset_type"],
    label: t(`catalog.types.${value}`),
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
  enabled: computed(
    () =>
      dialog.value &&
      !manual.value &&
      !editing.value &&
      tab.value === "instruments",
  ),
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
  if (tab.value === "assets") return !form.symbol.trim();
  if (!manual.value) return !editing.value && !selectedSpec.value;
  return (
    !form.symbol.trim() ||
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
function label(item: Asset | Instrument): string {
  return "exec_symbol" in item ? item.exec_symbol : item.symbol;
}
function archived(item: Asset | Instrument): boolean {
  return "is_archived" in item ? item.is_archived : !item.is_active;
}
function open(item: Asset | Instrument | null = null): void {
  editing.value = item;
  selectedSpec.value = undefined;
  importSymbol.value = "";
  cursor.value = undefined;
  Object.assign(form, {
    symbol: item ? label(item) : "",
    name: item?.name ?? "",
    asset_type: item && "asset_type" in item ? item.asset_type : "crypto",
    product: item && "product" in item ? item.product : "spot",
    base: item && "base_asset_id" in item ? item.base_asset_id : null,
    quote: item && "quote_asset_id" in item ? item.quote_asset_id : null,
    price_step: item && "price_step" in item ? item.price_step : "0.01",
    qty_step: item && "qty_step" in item ? item.qty_step : "0.001",
    min_qty: item && "min_qty" in item ? (item.min_qty ?? "") : "",
    min_notional:
      item && "min_notional" in item ? (item.min_notional ?? "") : "",
  });
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
    const name = form.name || null;
    if (tab.value === "assets")
      return editing.value
        ? updateAsset(props.profile.id, editing.value.id, { name })
        : createAsset(props.profile.id, {
            symbol: form.symbol,
            name,
            asset_type: form.asset_type,
          });
    const rules = {
      price_step: form.price_step,
      qty_step: form.qty_step,
      min_qty: form.min_qty || null,
      min_notional: form.min_notional || null,
    };
    if (editing.value)
      return updateInstrument(props.profile.id, editing.value.id, {
        name,
        ...(manual.value ? rules : {}),
      });
    if (!manual.value) {
      if (!selectedSpec.value) throw new Error(t("profileMarket.choose"));
      return createInstrument(props.profile.id, {
        exec_symbol: selectedSpec.value.symbol,
        product: selectedSpec.value.product,
        name,
      });
    }
    return createInstrument(props.profile.id, {
      exec_symbol: form.symbol,
      product: form.product,
      name,
      base_asset_id: form.base!,
      quote_asset_id: form.quote!,
      settlement_asset_id: form.quote!,
      ...rules,
    });
  },
  onSuccess: async () => {
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
    item: Asset | Instrument;
    kind: "archive" | "delete" | "refresh";
  }) => {
    if ("exec_symbol" in item) {
      if (kind === "refresh")
        return refreshInstrument(props.profile.id, item.id);
      if (kind === "delete") return deleteInstrument(props.profile.id, item.id);
      return updateInstrument(props.profile.id, item.id, {
        is_archived: !item.is_archived,
      });
    }
    if (kind === "delete") return deleteAsset(props.profile.id, item.id);
    return updateAsset(props.profile.id, item.id, {
      is_active: !item.is_active,
    });
  },
  onSuccess: async () => {
    await refresh();
    deleting.value = null;
  },
  onError: failed,
});
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
        v-if="!profile.is_archived && (manual || tab === 'instruments')"
        class="button button--primary"
        type="button"
        @click="open()"
      >
        <Plus :size="16" />{{
          $t(
            tab === "assets"
              ? "profileMarket.addAsset"
              : manual
                ? "profileMarket.addInstrument"
                : "profileMarket.import",
          )
        }}
      </button>
    </header>
    <nav class="profile-tabs" :aria-label="$t('profileMarket.title')">
      <button
        v-for="section in ['instruments', 'assets'] as const"
        :key="section"
        type="button"
        :class="{ 'profile-tabs__button--active': tab === section }"
        @click="tab = section"
      >
        {{ $t(`profileMarket.${section}`) }}
      </button>
    </nav>
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
              :direction="order"
              @sort="order = order === 'asc' ? 'desc' : 'asc'"
            />
            <th>{{ $t("profileMarket.details") }}</th>
            <th>{{ $t("profiles.status") }}</th>
            <th>
              <span class="sr-only">{{ $t("catalog.edit") }}</span>
            </th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="item in items" :key="item.id">
            <td :data-label="$t('profileMarket.symbol')">
              <strong>{{ label(item) }}</strong
              ><small v-if="item.name">{{ item.name }}</small>
            </td>
            <td :data-label="$t('profileMarket.details')">
              <template v-if="'product' in item"
                >{{ $t(`venues.products.${item.product}`)
                }}<small
                  >{{ $t("profileMarket.priceStep") }}
                  {{ formatDecimal(item.price_step) }} ·
                  {{ $t("profileMarket.qtyStep") }}
                  {{ formatDecimal(item.qty_step) }}</small
                ></template
              >
              <template v-else>{{
                $t(`catalog.types.${item.asset_type}`)
              }}</template>
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
            : tab === 'assets'
              ? 'profileMarket.addAsset'
              : manual
                ? 'profileMarket.addInstrument'
                : 'profileMarket.import',
        )
      "
      :submit-label="
        $t(
          !manual && !editing && tab === 'instruments'
            ? 'profileMarket.import'
            : 'catalog.saveChanges',
        )
      "
      :cancel-label="$t('common.cancel')"
      :busy="save.isPending.value"
      :invalid="invalid"
      @submit="save.mutate()"
    >
      <label v-if="tab === 'instruments'" class="field"
        ><span>{{ $t("profileMarket.product") }}</span>
        <AppSelect
          v-model="form.product"
          :options="products"
          :disabled="!!editing"
          :label="$t('profileMarket.product')"
      /></label>
      <template v-if="!manual && !editing && tab === 'instruments'">
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
      <template v-else>
        <label class="field"
          ><span>{{ $t("profileMarket.symbol") }}</span
          ><input
            v-model="form.symbol"
            :disabled="!!editing"
            :maxlength="tab === 'assets' ? 32 : 64"
        /></label>
        <label v-if="tab === 'assets'" class="field"
          ><span>{{ $t("profileMarket.assetType") }}</span
          ><AppSelect
            v-model="form.asset_type"
            :options="types"
            :disabled="!!editing"
            :label="$t('profileMarket.assetType')"
        /></label>
      </template>
      <label class="field"
        ><span>{{ $t("profileMarket.name") }}</span
        ><input v-model="form.name" maxlength="255"
      /></label>
      <template v-if="manual && tab === 'instruments'">
        <label class="field"
          ><span>{{ $t("profileMarket.base") }}</span
          ><RemoteCatalogSelect
            v-model="form.base"
            resource="assets"
            :profile-id="profile.id"
            :params="{ visibility: 'active' }"
            :exclude-id="form.quote"
            :disabled="!!editing"
            :placeholder="$t('profileMarket.chooseAsset')"
            :empty-label="$t('profileMarket.addAssetFirst')"
        /></label>
        <label class="field"
          ><span>{{ $t("profileMarket.quote") }}</span
          ><RemoteCatalogSelect
            v-model="form.quote"
            resource="assets"
            :profile-id="profile.id"
            :params="{ visibility: 'active' }"
            :exclude-id="form.base"
            :disabled="!!editing"
            :placeholder="$t('profileMarket.chooseAsset')"
            :empty-label="$t('profileMarket.addAssetFirst')"
        /></label>
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

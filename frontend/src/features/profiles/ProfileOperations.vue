<script setup lang="ts">
/** Profile-wide immutable ledger; asset selection is an explicit filter. */
import { computed, reactive, ref } from "vue";
import { useMutation, useQuery, useQueryClient } from "@tanstack/vue-query";
import { useI18n } from "vue-i18n";
import { Pencil, RotateCcw } from "@lucide/vue";
import AppSelect from "@/components/AppSelect.vue";
import PaginationControls from "@/components/PaginationControls.vue";
import SortableHeader from "@/components/SortableHeader.vue";
import LoadingState from "@/components/LoadingState.vue";
import ErrorState from "@/components/ErrorState.vue";
import EmptyState from "@/components/EmptyState.vue";
import FormDialog from "@/components/FormDialog.vue";
import { usePagination } from "@/composables/usePagination";
import { formatDecimal } from "@/utils/decimal";
import { useToastStore } from "@/stores/toasts";
import {
  listProfileOperations,
  updateOperationNote,
  type WalletOperationKind,
  type ProfileOperation,
} from "./api";

const props = defineProps<{
  profileId: number;
  assetId: number | null;
  assetSymbol: string;
}>();
const { t, locale } = useI18n();
const client = useQueryClient();
const toasts = useToastStore();
const filters = reactive({
  kind: "all" as "all" | WalletOperationKind,
  from: "",
  to: "",
});
const order = ref<"asc" | "desc">("desc");
const sortKey = ref<"created_at" | "kind">("created_at");
function sortBy(key: "created_at" | "kind"): void {
  order.value = sortKey.value === key && order.value === "asc" ? "desc" : "asc";
  sortKey.value = key;
}
const dateError = computed(
  () => filters.from && filters.to && filters.from > filters.to,
);
const criteria = computed(() => ({
  asset_id: props.assetId ?? undefined,
  kind: filters.kind === "all" ? undefined : filters.kind,
  date_from: filters.from || undefined,
  date_to: filters.to || undefined,
  order: order.value,
  sort: sortKey.value,
}));
const pagination = usePagination(
  computed(() => [props.profileId, criteria.value]),
);
const { page, pageSize } = pagination;
const key = computed(() => ["profiles", props.profileId, "operations"]);
const query = useQuery({
  queryKey: computed(() => [
    ...key.value,
    criteria.value,
    pagination.params.value,
  ]),
  queryFn: () =>
    listProfileOperations(props.profileId, {
      ...criteria.value,
      ...pagination.params.value,
    }),
  enabled: computed(() => props.assetId !== null && !dateError.value),
});
pagination.track(computed(() => query.data.value));
const kinds = computed(() => [
  { value: "all", label: t("profileMarket.allOperations") },
  ...(["deposit", "withdrawal"] as const).map((value) => ({
    value,
    label: t(`profiles.wallet.${value}`),
  })),
]);
const filtered = computed(
  () => filters.kind !== "all" || !!filters.from || !!filters.to,
);
function reset(): void {
  Object.assign(filters, { kind: "all", from: "", to: "" });
}
function dateLabel(value: string): string {
  return new Intl.DateTimeFormat(locale.value, {
    dateStyle: "medium",
    timeStyle: "short",
    hourCycle: "h23",
  }).format(
    new Date(/(?:Z|[+-]\d{2}:?\d{2})$/.test(value) ? value : `${value}Z`),
  );
}
const editing = ref<ProfileOperation | null>(null);
const dialog = ref(false);
const note = ref("");
function edit(item: ProfileOperation): void {
  editing.value = item;
  note.value = item.note ?? "";
  dialog.value = true;
}
const mutation = useMutation({
  mutationFn: () =>
    updateOperationNote(
      props.profileId,
      editing.value!.asset_id,
      editing.value!.id,
      note.value || null,
    ),
  onSuccess: async () => {
    await client.invalidateQueries({ queryKey: key.value });
    dialog.value = false;
    toasts.success({ title: t("profiles.wallet.noteSaved") });
  },
  onError: () => toasts.error({ title: t("profiles.wallet.saveFailed") }),
});
</script>

<template>
  <section v-if="assetId !== null" class="profile-ledger">
    <header class="profile-panel__header">
      <div>
        <h4>{{ $t("profileMarket.assetLedger", { symbol: assetSymbol }) }}</h4>
        <p>{{ $t("profileMarket.ledgerHelp") }}</p>
      </div>
    </header>
    <div class="profile-toolbar ledger-filters">
      <AppSelect
        v-model="filters.kind"
        :options="kinds"
        :label="$t('profileMarket.allOperations')"
      />
      <label class="field"
        ><span>{{ $t("trades.filters.from") }}</span>
        <input v-model="filters.from" type="date"
      /></label>
      <label class="field"
        ><span>{{ $t("trades.filters.to") }}</span>
        <input v-model="filters.to" type="date"
      /></label>
      <button
        class="button button--secondary ledger-reset"
        type="button"
        :aria-label="$t('catalog.reset')"
        :title="$t('catalog.reset')"
        @click="reset"
      >
        <RotateCcw :size="16" />
      </button>
    </div>
    <p v-if="dateError" class="field-error">
      {{ $t("analytics.filters.dateOrder") }}
    </p>
    <template v-else>
      <LoadingState v-if="query.isPending.value" />
      <ErrorState v-else-if="query.isError.value" @retry="query.refetch()" />
      <EmptyState
        v-else-if="query.data.value?.total === 0"
        :title="
          $t(
            filtered
              ? 'profileMarket.noFilteredOperations'
              : 'profiles.wallet.noOperations',
          )
        "
        :description="
          $t(
            filtered
              ? 'workspaceEmpty.filteredTrades.description'
              : 'profileMarket.operationsHelp',
          )
        "
      >
        <button v-if="filtered" class="button button--secondary" @click="reset">
          {{ $t("catalog.reset") }}
        </button>
      </EmptyState>
      <div v-else class="table-scroll">
        <table class="catalog-table">
          <thead>
            <tr>
              <SortableHeader
                :label="$t('profileMarket.operationDate')"
                :direction="sortKey === 'created_at' ? order : null"
                @sort="sortBy('created_at')"
              />
              <SortableHeader
                :label="$t('profileMarket.operationType')"
                :direction="sortKey === 'kind' ? order : null"
                @sort="sortBy('kind')"
              />
              <th>{{ $t("profiles.wallet.amount") }}</th>
              <th>{{ $t("profiles.wallet.note") }}</th>
              <th>
                <span class="sr-only">{{ $t("catalog.edit") }}</span>
              </th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="item in query.data.value?.items" :key="item.id">
              <td :data-label="$t('profileMarket.operationDate')">
                {{ dateLabel(item.created_at) }}
              </td>
              <td :data-label="$t('profileMarket.operationType')">
                <span
                  class="catalog-tag"
                  :class="`ledger-kind--${item.kind}`"
                  >{{ $t(`profiles.wallet.${item.kind}`) }}</span
                >
              </td>
              <td
                :data-label="$t('profiles.wallet.amount')"
                class="numeric-cell ledger-row__amount"
                :class="`ledger-row__amount--${item.kind}`"
              >
                {{ item.kind === "deposit" ? "+" : ""
                }}{{ formatDecimal(item.amount) }}
              </td>
              <td :data-label="$t('profiles.wallet.note')">
                {{ item.note || "—" }}
              </td>
              <td>
                <button
                  class="icon-action"
                  type="button"
                  :aria-label="$t('profiles.wallet.editNote')"
                  @click="edit(item)"
                >
                  <Pencil :size="15" />
                </button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
      <PaginationControls
        v-if="query.isSuccess.value"
        v-model:page="page"
        v-model:page-size="pageSize"
        :total="query.data.value?.total ?? 0"
        :busy="query.isFetching.value"
      />
    </template>
    <FormDialog
      v-model:open="dialog"
      :title="$t('profiles.wallet.editNote')"
      :description="$t('profiles.wallet.noteOnly')"
      :cancel-label="$t('common.cancel')"
      :submit-label="$t('catalog.saveChanges')"
      :busy="mutation.isPending.value"
      @submit="mutation.mutate()"
    >
      <label class="field"
        ><span>{{ $t("profiles.wallet.note") }}</span>
        <textarea v-model="note" maxlength="255" />
      </label>
    </FormDialog>
  </section>
</template>

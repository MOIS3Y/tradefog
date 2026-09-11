<script setup lang="ts">
import { Plus, RotateCcw, Search, SlidersHorizontal } from "@lucide/vue";
import { useQuery } from "@tanstack/vue-query";
import { computed, ref, watch, onBeforeUnmount } from "vue";
import { useI18n } from "vue-i18n";
import { useRoute, useRouter } from "vue-router";
import { useProfilePresence } from "@/composables/useProfilePresence";
import { hasTradeFilters } from "./filters";
import AppSelect from "@/components/AppSelect.vue";
import EmptyState from "@/components/EmptyState.vue";
import ErrorState from "@/components/ErrorState.vue";
import LoadingState from "@/components/LoadingState.vue";
import PanelHeading from "@/components/PanelHeading.vue";
import { ChartCandlestick } from "@lucide/vue";
import PaginationControls from "@/components/PaginationControls.vue";
import SearchableSelect from "@/components/SearchableSelect.vue";
import SortableHeader from "@/components/SortableHeader.vue";
import { listProfiles, listStrategies } from "@/features/profiles/api";
import { listTrades, type TradeListParams } from "@/features/trades/api";
import TradeCreateDialog from "./TradeCreateDialog.vue";
import TradeRatingDisplay from "@/features/trades/TradeRatingDisplay.vue";
import { formatDecimal } from "@/utils/decimal";

const { t } = useI18n();
const route = useRoute();
const router = useRouter();
const creating = ref(false);
watch(
  () => route.query.create,
  (value) => {
    if (value !== "1") return;
    creating.value = true;
    void router.replace({ query: { ...route.query, create: undefined } });
  },
  { immediate: true },
);
const text = (key: string, fallback = "") =>
  typeof route.query[key] === "string" ? String(route.query[key]) : fallback;
const positive = (key: string, fallback: number): number => {
  const value = Number(text(key));
  return Number.isSafeInteger(value) && value > 0 ? value : fallback;
};
function change(key: string, value: string | number | null): void {
  void router.replace({
    query: {
      ...route.query,
      page: undefined,
      [key]:
        value === null || value === "all" || value === ""
          ? undefined
          : String(value),
    },
  });
}
function field(key: string, fallback = "all") {
  return computed({
    get: () => text(key, fallback),
    set: (value: string) => change(key, value),
  });
}
const status = field("trade_status");
const review = field("review");
const rating = field("rating");
const direction = field("direction");
const period = field("period");
const from = field("date_from", "");
const to = field("date_to", "");
const profileId = computed({
  get: () => Number(text("profile_id")) || null,
  set: (value: number | null) => {
    void router.replace({
      query: {
        ...route.query,
        page: undefined,
        strategy_id: undefined,
        profile_id: value ? String(value) : undefined,
      },
    });
  },
});
const strategyId = computed({
  get: () => Number(text("strategy_id")) || null,
  set: (value: number | null) => change("strategy_id", value),
});
const page = computed({
  get: () => positive("page", 1),
  set: (value: number) => change("page", value),
});
const pageSize = computed({
  get: () =>
    [25, 50, 100].includes(positive("page_size", 25))
      ? positive("page_size", 25)
      : 25,
  set: (value: number) => change("page_size", value),
});
const search = ref(text("q"));
let timer: ReturnType<typeof setTimeout> | undefined;
watch(search, (value) => {
  clearTimeout(timer);
  timer = setTimeout(() => {
    if (value !== text("q")) change("q", value);
  }, 250);
});
watch(
  () => route.query.q,
  () => {
    search.value = text("q");
  },
);
onBeforeUnmount(() => clearTimeout(timer));
const profilesQuery = useQuery({
  queryKey: ["profiles"],
  queryFn: listProfiles,
});
const profileOptions = computed(() =>
  (profilesQuery.data.value ?? []).map((x) => ({ value: x.id, label: x.name })),
);
const strategiesQuery = useQuery({
  queryKey: computed(() => ["profiles", profileId.value, "strategies"]),
  enabled: computed(() => profileId.value !== null),
  queryFn: () => listStrategies(profileId.value!),
});
const strategyOptions = computed(() =>
  (strategiesQuery.data.value ?? []).map((x) => ({
    value: x.id,
    label: x.name,
  })),
);
const statusOptions = computed(() =>
  ["all", "draft", "pending_entry", "open", "closed", "cancelled"].map(
    (value) => ({
      value,
      label: t(
        value === "all"
          ? "trades.filters.allStatuses"
          : `trades.status.${value}`,
      ),
    }),
  ),
);
const reviewOptions = computed(() =>
  ["all", "reviewed", "unreviewed"].map((value) => ({
    value,
    label: t(`journal.review.${value}`),
  })),
);
const ratingOptions = computed(() =>
  ["all", "rated", "unrated"].map((value) => ({
    value,
    label: t(`journal.rating.${value}`),
  })),
);
const directionOptions = computed(() =>
  ["all", "long", "short"].map((value) => ({
    value,
    label: t(
      value === "all" ? "journal.allDirections" : `trades.direction.${value}`,
    ),
  })),
);
const periodOptions = computed(() =>
  ["all", "week", "month", "quarter", "custom"].map((value) => ({
    value,
    label: t(`trades.period.${value}`),
  })),
);
const criteria = computed<TradeListParams>(() => {
  let dateFrom =
    period.value === "custom" ? from.value || undefined : undefined;
  if (["week", "month", "quarter"].includes(period.value)) {
    const date = new Date();
    date.setDate(
      date.getDate() -
        (period.value === "week" ? 7 : period.value === "month" ? 30 : 90) +
        1,
    );
    dateFrom = date.toISOString().slice(0, 10);
  }
  return {
    q: text("q"),
    page: page.value,
    page_size: pageSize.value,
    sort: text("sort", "trade_date"),
    order: text("order") === "asc" ? "asc" : "desc",
    trade_status:
      status.value === "all"
        ? undefined
        : (status.value as TradeListParams["trade_status"]),
    review: review.value as TradeListParams["review"],
    rated: rating.value === "all" ? undefined : rating.value === "rated",
    direction:
      direction.value === "all"
        ? undefined
        : (direction.value as TradeListParams["direction"]),
    profile_id: profileId.value ?? undefined,
    strategy_id: strategyId.value ?? undefined,
    date_from: dateFrom,
    date_to: period.value === "custom" ? to.value || undefined : undefined,
  };
});
const dateError = computed(
  () =>
    period.value === "custom" &&
    from.value &&
    to.value &&
    from.value > to.value,
);
const query = useQuery({
  queryKey: computed(() => ["trades", "list", criteria.value]),
  queryFn: () => listTrades(criteria.value),
  enabled: computed(() => !dateError.value),
});
watch(
  () => query.data.value,
  (value) => {
    if (
      value &&
      page.value > Math.max(1, Math.ceil(value.total / pageSize.value))
    )
      page.value = Math.max(1, Math.ceil(value.total / pageSize.value));
  },
);
const filtered = computed(() => hasTradeFilters(criteria.value));
const needsProfiles = computed(
  () =>
    query.isSuccess.value && query.data.value?.total === 0 && !filtered.value,
);
const needsPresence = computed(
  () =>
    needsProfiles.value &&
    profilesQuery.isSuccess.value &&
    profilesQuery.data.value?.length === 0,
);
const presence = useProfilePresence(needsPresence);
const emptyPending = computed(
  () =>
    needsProfiles.value &&
    (profilesQuery.isPending.value ||
      (needsPresence.value && presence.isPending.value)),
);
const emptyError = computed(
  () =>
    needsProfiles.value &&
    (profilesQuery.isError.value ||
      (needsPresence.value && presence.isError.value)),
);
const emptyKind = computed(() => {
  if (filtered.value) return "filteredTrades";
  if (profilesQuery.data.value?.length) return "trades";
  return presence.data.value?.total ? "archivedProfiles" : "start";
});
const columns = [
  ["trade_date", "trades.fields.date"],
  ["instrument", "trades.fields.instrument"],
  ["profile", "trades.fields.profile"],
  ["strategy", "trades.fields.strategy"],
  ["status", "trades.filters.status"],
] as const;
function sort(key: string): void {
  void router.replace({
    query: {
      ...route.query,
      page: undefined,
      sort: key,
      order:
        text("sort", "trade_date") === key && text("order", "desc") === "desc"
          ? "asc"
          : "desc",
    },
  });
}
function active(key: string): "asc" | "desc" | null {
  return text("sort", "trade_date") === key
    ? text("order", "desc") === "asc"
      ? "asc"
      : "desc"
    : null;
}
const backQuery = computed(() => ({ returnTo: route.fullPath }));
const advancedCount = computed(
  () =>
    [
      profileId.value !== null,
      strategyId.value !== null,
      direction.value !== "all",
      review.value !== "all",
      rating.value !== "all",
    ].filter(Boolean).length,
);
const advancedOpen = ref(advancedCount.value > 0);
</script>

<template>
  <section class="trade-shell">
    <PanelHeading
      embedded
      :icon="ChartCandlestick"
      :title="$t('journal.title')"
      :description="$t('pageDescriptions.trades')"
    >
      <button
        class="button button--primary trade-toolbar__create"
        type="button"
        @click="creating = true"
      >
        <Plus :size="17" />{{ $t("trades.new") }}
      </button>
    </PanelHeading>
    <div class="trade-toolbar journal-toolbar">
      <label class="search-field trade-search"
        ><Search
          class="search-field__icon"
          :size="17"
          aria-hidden="true" /><input
          v-model="search"
          :aria-label="$t('trades.filters.search')"
          :placeholder="$t('trades.filters.search')"
      /></label>
      <AppSelect
        v-model="status"
        :options="statusOptions"
        :label="$t('trades.filters.status')"
      />
      <AppSelect
        v-model="period"
        :options="periodOptions"
        :label="$t('trades.filters.period')"
      />
      <button
        class="button button--secondary journal-more"
        :class="{ 'button--active': advancedOpen }"
        type="button"
        :aria-expanded="advancedOpen"
        aria-controls="trade-extra-filters"
        @click="advancedOpen = !advancedOpen"
      >
        <SlidersHorizontal :size="16" aria-hidden="true" />
        {{ $t("analytics.filters.more")
        }}<span v-if="advancedCount">({{ advancedCount }})</span>
      </button>
      <button
        class="button button--secondary journal-reset"
        type="button"
        :aria-label="$t('catalog.reset')"
        :title="$t('catalog.reset')"
        @click="router.replace('/trades')"
      >
        <RotateCcw :size="16" aria-hidden="true" />
      </button>
    </div>
    <div
      v-show="advancedOpen"
      id="trade-extra-filters"
      class="trade-toolbar journal-toolbar"
    >
      <SearchableSelect
        class="journal-filter-selector"
        v-model="profileId"
        :options="profileOptions"
        :placeholder="$t('journal.allProfiles')"
        :empty-label="$t('trades.fields.noProfiles')"
      />
      <SearchableSelect
        class="journal-filter-selector"
        v-model="strategyId"
        :options="strategyOptions"
        :disabled="profileId === null"
        :placeholder="$t('journal.allStrategies')"
        :empty-label="$t('trades.fields.noStrategies')"
      />
      <AppSelect
        v-model="direction"
        :options="directionOptions"
        :label="$t('journal.allDirections')"
      />
      <AppSelect
        v-model="review"
        :options="reviewOptions"
        :label="$t('journal.reviewLabel')"
      />
      <AppSelect
        v-model="rating"
        :options="ratingOptions"
        :label="$t('trades.rating.label')"
      />
    </div>
    <div v-if="period === 'custom'" class="trade-toolbar journal-toolbar">
      <label class="field"
        ><span>{{ $t("trades.filters.from") }}</span
        ><input v-model="from" type="date"
      /></label>
      <label class="field"
        ><span>{{ $t("trades.filters.to") }}</span
        ><input v-model="to" type="date"
      /></label>
      <p v-if="dateError" class="field-error">
        {{ $t("analytics.filters.dateOrder") }}
      </p>
    </div>
    <template v-if="!dateError">
      <LoadingState v-if="query.isPending.value || emptyPending" />
      <ErrorState
        v-else-if="query.isError.value || emptyError"
        @retry="
          query.refetch();
          profilesQuery.refetch();
          presence.refetch();
        "
      />
      <EmptyState
        v-else-if="query.data.value?.total === 0"
        :title="
          filtered
            ? $t('trades.emptyFiltered')
            : $t(`workspaceEmpty.${emptyKind}.title`)
        "
        :description="$t(`workspaceEmpty.${emptyKind}.description`)"
      >
        <button
          v-if="filtered"
          class="button button--secondary"
          @click="router.replace('/trades')"
        >
          {{ $t("catalog.reset") }}
        </button>
        <button
          v-else-if="emptyKind === 'trades'"
          class="button button--primary"
          @click="creating = true"
        >
          {{ $t("workspaceEmpty.trades.action") }}
        </button>
        <RouterLink v-else class="button button--primary" to="/profiles">{{
          $t(`workspaceEmpty.${emptyKind}.action`)
        }}</RouterLink>
      </EmptyState>
      <div v-else class="catalog-table-wrap">
        <table class="catalog-table journal-table">
          <thead>
            <tr>
              <SortableHeader
                v-for="[key, label] in columns"
                :key="key"
                :label="$t(label)"
                :direction="active(key)"
                @sort="sort(key)"
              />
              <th>{{ $t("journal.pnl") }}</th>
              <SortableHeader
                :label="$t('trades.rating.label')"
                :direction="active('quality_rating')"
                @sort="sort('quality_rating')"
              />
              <SortableHeader
                :label="$t('journal.reviewLabel')"
                :direction="active('review_completed_at')"
                @sort="sort('review_completed_at')"
              />
            </tr>
          </thead>
          <tbody>
            <tr v-for="trade in query.data.value?.items" :key="trade.id">
              <td :data-label="$t('trades.fields.date')">
                <time>{{ trade.trade_date }}</time>
              </td>
              <td :data-label="$t('trades.fields.instrument')">
                <div class="journal-identity">
                  <RouterLink
                    class="catalog-symbol"
                    :to="{ path: `/trades/${trade.id}`, query: backQuery }"
                    >{{ trade.pair_symbol }}</RouterLink
                  ><small
                    >{{ trade.exec_symbol }} ·
                    <span :class="`direction-badge--${trade.direction}`">{{
                      $t(`trades.direction.${trade.direction}`)
                    }}</span></small
                  >
                </div>
              </td>
              <td :data-label="$t('trades.fields.profile')">
                {{ trade.profile_name }}
              </td>
              <td :data-label="$t('trades.fields.strategy')">
                {{ trade.strategy_name }}
              </td>
              <td :data-label="$t('trades.filters.status')">
                <span :class="`trade-status trade-status--${trade.status}`">{{
                  $t(`trades.status.${trade.status}`)
                }}</span>
              </td>
              <td :data-label="$t('journal.pnl')">
                <span class="journal-pnl">{{
                  trade.realized_pnl === null
                    ? "—"
                    : `${formatDecimal(trade.realized_pnl)} ${trade.settlement_symbol}`
                }}</span>
              </td>
              <td :data-label="$t('trades.rating.label')">
                <TradeRatingDisplay :value="trade.quality_rating" />
              </td>
              <td :data-label="$t('journal.reviewLabel')">
                <span
                  class="catalog-tag"
                  :class="{ 'catalog-tag--active': trade.review_completed_at }"
                  >{{
                    trade.review_completed_at
                      ? $t("journal.review.reviewed")
                      : trade.status === "closed"
                        ? $t("journal.review.unreviewed")
                        : "—"
                  }}</span
                >
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
    </template>
    <TradeCreateDialog
      v-if="creating"
      :return-to="route.fullPath"
      @close="creating = false"
    />
  </section>
</template>

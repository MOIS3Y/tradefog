<script setup lang="ts">
import {
  CalendarRange,
  Plus,
  Search,
  TrendingDown,
  TrendingUp,
} from "@lucide/vue";
import { useMutation, useQuery, useQueryClient } from "@tanstack/vue-query";
import { computed, reactive, ref, watch } from "vue";
import { useI18n } from "vue-i18n";
import { useRouter } from "vue-router";

import { ApiError } from "@/api/errors";
import AppSelect, { type SelectOption } from "@/components/AppSelect.vue";
import EmptyState from "@/components/EmptyState.vue";
import ErrorState from "@/components/ErrorState.vue";
import FormDialog from "@/components/FormDialog.vue";
import LoadingState from "@/components/LoadingState.vue";
import SearchableSelect, {
  type SearchableOption,
} from "@/components/SearchableSelect.vue";
import { listProfiles, listStrategies } from "@/features/profiles/api";
import TradeEditor from "@/features/trades/TradeEditor.vue";
import {
  createTrade,
  listTrades,
  type Direction,
  type Trade,
  type TradeStatus,
} from "@/features/trades/api";
import { listInstruments, listVenues } from "@/features/venues/api";
import { useToastStore } from "@/stores/toasts";

type Period = "all" | "week" | "month" | "quarter" | "custom";
type StatusFilter = TradeStatus | "all";

const { t } = useI18n();
const router = useRouter();
const queryClient = useQueryClient();
const toasts = useToastStore();
const selectedId = ref<number | null>(null);
const search = ref("");
const statusFilter = ref<StatusFilter>("all");
const period = ref<Period>("all");
const dateFrom = ref("");
const dateTo = ref("");
const dialogOpen = ref(false);
const form = reactive({
  profile_id: null as number | null,
  strategy_id: null as number | null,
  venue_instrument_id: null as number | null,
  trade_date: new Date().toISOString().slice(0, 10),
  direction: "long" as Direction,
});

const tradesQuery = useQuery({ queryKey: ["trades"], queryFn: listTrades });
const profilesQuery = useQuery({
  queryKey: ["profiles"],
  queryFn: listProfiles,
});
const venuesQuery = useQuery({
  queryKey: ["catalog", "venues"],
  queryFn: listVenues,
});
const profiles = computed(() => profilesQuery.data.value ?? []);
const activeProfiles = computed(() =>
  profiles.value.filter((profile) => !profile.is_archived),
);
const venues = computed(() => venuesQuery.data.value ?? []);

const strategiesQuery = useQuery({
  queryKey: computed(() => [
    "trade-strategies",
    profiles.value.map((x) => x.id),
  ]),
  enabled: computed(() => profiles.value.length > 0),
  queryFn: async () =>
    (
      await Promise.all(
        profiles.value.map(async (profile) => ({
          profileId: profile.id,
          items: await listStrategies(profile.id),
        })),
      )
    ).flatMap(({ profileId, items }) =>
      items.map((item) => ({ ...item, profileId })),
    ),
});
const instrumentsQuery = useQuery({
  queryKey: computed(() => [
    "trade-instruments",
    venues.value.map((x) => x.id),
  ]),
  enabled: computed(() => venues.value.length > 0),
  queryFn: async () =>
    (
      await Promise.all(venues.value.map((venue) => listInstruments(venue.id)))
    ).flat(),
});
const strategies = computed(() => strategiesQuery.data.value ?? []);
const instruments = computed(() => instrumentsQuery.data.value ?? []);
const profileById = computed(
  () => new Map(profiles.value.map((item) => [item.id, item])),
);
const strategyById = computed(
  () => new Map(strategies.value.map((item) => [item.id, item])),
);
const instrumentById = computed(
  () => new Map(instruments.value.map((item) => [item.id, item])),
);
const venueById = computed(
  () => new Map(venues.value.map((item) => [item.id, item])),
);

const statusOptions = computed<SelectOption<StatusFilter>[]>(() => [
  { value: "all", label: t("trades.filters.allStatuses") },
  ...(["draft", "pending_entry", "open", "closed", "cancelled"] as const).map(
    (value) => ({ value, label: t(`trades.status.${value}`) }),
  ),
]);
const periodOptions = computed<SelectOption<Period>[]>(() =>
  (["all", "week", "month", "quarter", "custom"] as const).map((value) => ({
    value,
    label: t(`trades.period.${value}`),
  })),
);
const profileOptions = computed<SearchableOption[]>(() =>
  activeProfiles.value.map((profile) => ({
    value: profile.id,
    label: profile.name,
    detail: venueById.value.get(profile.venue_id)?.name,
  })),
);
const selectedProfile = computed(() =>
  profiles.value.find((item) => item.id === form.profile_id),
);
const availableStrategies = computed(() =>
  strategies.value.filter(
    (strategy) =>
      strategy.profile_id === form.profile_id &&
      !strategy.is_archived &&
      strategy.allocations.some((allocation) => !allocation.is_archived),
  ),
);
const strategyOptions = computed<SearchableOption[]>(() =>
  availableStrategies.value.map((strategy) => ({
    value: strategy.id,
    label: strategy.name,
    detail: `${strategy.risk_percent}% · 1:${strategy.reward_multiple}`,
  })),
);
const availableInstruments = computed(() =>
  instruments.value.filter(
    (instrument) =>
      instrument.venue_id === selectedProfile.value?.venue_id &&
      instrument.is_active,
  ),
);
const instrumentOptions = computed<SearchableOption[]>(() =>
  availableInstruments.value.map((instrument) => ({
    value: instrument.id,
    label: instrument.pair.canonical_symbol,
    detail: `${t(`venues.products.${instrument.product}`)} · ${instrument.exec_symbol}`,
  })),
);

function rangeStart(): string | null {
  if (period.value === "all") return null;
  if (period.value === "custom") return dateFrom.value || null;
  const days = period.value === "week" ? 7 : period.value === "month" ? 30 : 90;
  const start = new Date();
  start.setDate(start.getDate() - days + 1);
  return start.toISOString().slice(0, 10);
}

const filtered = computed(() => {
  const needle = search.value.trim().toLocaleLowerCase();
  const from = rangeStart();
  const to = period.value === "custom" ? dateTo.value || null : null;
  return (tradesQuery.data.value ?? []).filter((trade) => {
    const profile = profileById.value.get(trade.profile_id)?.name ?? "";
    const strategy = strategyById.value.get(trade.strategy_id)?.name ?? "";
    const instrument = instrumentById.value.get(trade.venue_instrument_id);
    const identity = `${instrument?.pair.canonical_symbol ?? ""} ${instrument?.exec_symbol ?? ""} ${profile} ${strategy}`;
    return (
      (statusFilter.value === "all" || trade.status === statusFilter.value) &&
      (!from || trade.trade_date >= from) &&
      (!to || trade.trade_date <= to) &&
      identity.toLocaleLowerCase().includes(needle)
    );
  });
});
const selected = computed(
  () =>
    (tradesQuery.data.value ?? []).find(
      (trade) => trade.id === selectedId.value,
    ) ?? null,
);
const setupReady = computed(
  () =>
    activeProfiles.value.length > 0 &&
    strategies.value.some(
      (item) =>
        !item.is_archived && item.allocations.some((x) => !x.is_archived),
    ) &&
    instruments.value.some((item) => item.is_active),
);
const formInvalid = computed(
  () =>
    form.profile_id === null ||
    form.strategy_id === null ||
    form.venue_instrument_id === null ||
    form.trade_date.length === 0,
);

watch(
  filtered,
  (items) => {
    if (!items.some((item) => item.id === selectedId.value)) {
      selectedId.value = items[0]?.id ?? null;
    }
  },
  { immediate: true },
);
watch(
  () => form.profile_id,
  () => {
    form.strategy_id = null;
    form.venue_instrument_id = null;
  },
);

function reportError(error: unknown, title: string): void {
  toasts.error({
    title,
    description:
      error instanceof ApiError ? error.message : t("trades.errors.generic"),
  });
}

const createMutation = useMutation({
  mutationFn: () =>
    createTrade({
      profile_id: form.profile_id ?? 0,
      strategy_id: form.strategy_id ?? 0,
      venue_instrument_id: form.venue_instrument_id ?? 0,
      trade_date: form.trade_date,
      direction: form.direction,
      description_markdown: null,
    }),
  onSuccess: async (trade) => {
    await queryClient.invalidateQueries({ queryKey: ["trades"] });
    selectedId.value = trade.id;
    dialogOpen.value = false;
    toasts.success({ title: t("trades.created"), description: `#${trade.id}` });
  },
  onError: (error) => reportError(error, t("trades.createFailed")),
});

function applyTradeUpdate(trade: Trade): void {
  queryClient.setQueryData<Trade[]>(["trades"], (current) =>
    current?.map((item) => (item.id === trade.id ? trade : item)),
  );
}

function openCreate(): void {
  if (!setupReady.value) {
    void router.push("/profiles");
    return;
  }
  Object.assign(form, {
    profile_id: null,
    strategy_id: null,
    venue_instrument_id: null,
    trade_date: new Date().toISOString().slice(0, 10),
    direction: "long",
  });
  dialogOpen.value = true;
}
</script>

<template>
  <section class="trade-shell">
    <div class="trade-toolbar">
      <label class="search-field trade-search">
        <Search class="search-field__icon" :size="17" aria-hidden="true" />
        <input v-model="search" :placeholder="$t('trades.filters.search')" />
      </label>
      <AppSelect
        v-model="statusFilter"
        :options="statusOptions"
        :label="$t('trades.filters.status')"
      />
      <AppSelect
        v-model="period"
        :options="periodOptions"
        :label="$t('trades.filters.period')"
      />
      <div v-if="period === 'custom'" class="trade-date-range">
        <CalendarRange :size="16" aria-hidden="true" />
        <input
          v-model="dateFrom"
          type="date"
          :aria-label="$t('trades.filters.from')"
        />
        <span>—</span>
        <input
          v-model="dateTo"
          type="date"
          :aria-label="$t('trades.filters.to')"
        />
      </div>
      <button
        class="button button--primary trade-toolbar__create"
        type="button"
        @click="openCreate"
      >
        <Plus :size="17" aria-hidden="true" />
        {{ $t("trades.new") }}
      </button>
    </div>

    <LoadingState
      v-if="tradesQuery.isPending.value || profilesQuery.isPending.value"
    />
    <ErrorState
      v-else-if="tradesQuery.isError.value"
      @retry="tradesQuery.refetch()"
    />
    <div v-else class="trade-console">
      <aside class="trade-directory">
        <div class="trade-directory__count">
          {{ $t("trades.found", { count: filtered.length }) }}
        </div>
        <button
          v-for="trade in filtered"
          :key="trade.id"
          class="trade-card"
          :class="{ 'trade-card--selected': trade.id === selectedId }"
          type="button"
          @click="selectedId = trade.id"
        >
          <span
            class="trade-card__direction"
            :class="`trade-card__direction--${trade.direction}`"
          >
            <TrendingUp v-if="trade.direction === 'long'" :size="17" />
            <TrendingDown v-else :size="17" />
          </span>
          <span class="trade-card__identity">
            <strong>{{
              instrumentById.get(trade.venue_instrument_id)?.pair
                .canonical_symbol ?? `#${trade.id}`
            }}</strong>
            <small
              >{{ profileById.get(trade.profile_id)?.name }} ·
              {{ strategyById.get(trade.strategy_id)?.name }}</small
            >
          </span>
          <span class="trade-card__meta">
            <em :class="`trade-status trade-status--${trade.status}`">{{
              $t(`trades.status.${trade.status}`)
            }}</em>
            <time>{{ trade.trade_date }}</time>
          </span>
        </button>
        <p v-if="filtered.length === 0" class="trade-directory__empty">
          {{ $t("trades.emptyFiltered") }}
        </p>
      </aside>

      <TradeEditor
        v-if="selected"
        :key="selected.id"
        :trade="selected"
        :profile="profileById.get(selected.profile_id)"
        :strategy="strategyById.get(selected.strategy_id)"
        :instrument="instrumentById.get(selected.venue_instrument_id)"
        :profiles="activeProfiles"
        :strategies="strategies"
        :instruments="instruments"
        @updated="applyTradeUpdate"
        @deleted="
          selectedId = null;
          queryClient.invalidateQueries({ queryKey: ['trades'] });
        "
      />
      <EmptyState
        v-else
        :title="$t('trades.emptyTitle')"
        :body="$t('trades.emptyBody')"
      >
        <button
          class="button button--primary"
          type="button"
          @click="openCreate"
        >
          {{ $t("trades.new") }}
        </button>
      </EmptyState>
    </div>
  </section>

  <FormDialog
    v-model:open="dialogOpen"
    :title="$t('trades.createTitle')"
    :description="$t('trades.createBody')"
    :submit-label="$t('trades.createDraft')"
    :cancel-label="$t('common.cancel')"
    :busy="createMutation.isPending.value"
    :invalid="formInvalid"
    @submit="createMutation.mutate()"
  >
    <label class="field"
      ><span>{{ $t("trades.fields.profile") }}</span
      ><SearchableSelect
        v-model="form.profile_id"
        :options="profileOptions"
        :placeholder="$t('trades.fields.selectProfile')"
        :empty-label="$t('trades.fields.noProfiles')"
    /></label>
    <label class="field"
      ><span>{{ $t("trades.fields.strategy") }}</span
      ><SearchableSelect
        v-model="form.strategy_id"
        :options="strategyOptions"
        :disabled="form.profile_id === null"
        :placeholder="$t('trades.fields.selectStrategy')"
        :empty-label="$t('trades.fields.noStrategies')"
    /></label>
    <label class="field"
      ><span>{{ $t("trades.fields.instrument") }}</span
      ><SearchableSelect
        v-model="form.venue_instrument_id"
        :options="instrumentOptions"
        :disabled="form.profile_id === null"
        :placeholder="$t('trades.fields.selectInstrument')"
        :empty-label="$t('trades.fields.noInstruments')"
    /></label>
    <label class="field"
      ><span>{{ $t("trades.fields.date") }}</span
      ><input v-model="form.trade_date" type="date" required
    /></label>
  </FormDialog>
</template>

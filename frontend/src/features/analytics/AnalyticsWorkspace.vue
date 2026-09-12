<script setup lang="ts">
import RemoteCatalogSelect from "@/components/RemoteCatalogSelect.vue";
import {
  Activity,
  ArrowRight,
  ChartNoAxesCombined,
  Gauge,
  Landmark,
  RotateCcw,
  SlidersHorizontal,
} from "@lucide/vue";
import { useQuery } from "@tanstack/vue-query";
import Decimal from "decimal.js";
import type { EChartsCoreOption } from "echarts/core";
import { computed, reactive, ref, watch } from "vue";
import { useI18n } from "vue-i18n";
import { useRoute, useRouter } from "vue-router";

import AppSelect, { type SelectOption } from "@/components/AppSelect.vue";
import EmptyState from "@/components/EmptyState.vue";
import ErrorState from "@/components/ErrorState.vue";
import LoadingState from "@/components/LoadingState.vue";
import SearchableSelect, {
  type SearchableOption,
} from "@/components/SearchableSelect.vue";
import AnalyticsChart from "@/features/analytics/AnalyticsChart.vue";
import MetricHelp from "@/features/analytics/MetricHelp.vue";
import {
  getAnalytics,
  type Analytics,
  type AnalyticsFilters,
  type AnalyticsPeriod,
  type ProductKind,
} from "@/features/analytics/api";
import {
  buildDisciplineSeries,
  buildMonetarySeries,
  buildOverviewSeries,
  type ChartPoint,
} from "@/features/analytics/chartData";
import {
  getWallet,
  getProfile,
  listProfiles,
  listStrategies,
} from "@/features/profiles/api";
import { formatDecimal, formatRoundedDecimal } from "@/utils/decimal";

type Tab = "overview" | "discipline" | "money";
type ProductChoice = ProductKind | "all";

interface TooltipParameter {
  data?: ChartPoint;
}

const { t, locale } = useI18n();
const router = useRouter();
const route = useRoute();
const activeProfileId = Number(route.params.profileId) || null;
const tabs: Tab[] = ["overview", "discipline", "money"];
const activeTab = ref<Tab>("overview");
const advancedOpen = ref(false);
const selectedMoneyId = ref<number | null>(null);
const productChoice = ref<ProductChoice>("all");
const filters = reactive<AnalyticsFilters>({
  period: "all_time",
  dateFrom: null,
  dateTo: null,
  profileId: activeProfileId,
  strategyId: null,
  product: null,
  instrumentId: null,
  settlementAssetId: null,
  strategyCapitalId: null,
});

const queryFields = {
  period: "period",
  dateFrom: "date_from",
  dateTo: "date_to",
  profileId: "profile_id",
  strategyId: "strategy_id",
  product: "product",
  instrumentId: "instrument_id",
  settlementAssetId: "settlement_asset_id",
  strategyCapitalId: "strategy_capital_id",
} as const;
for (const [field, parameter] of Object.entries(queryFields)) {
  if (field === "profileId" && activeProfileId !== null) continue;
  const value = route.query[parameter];
  if (typeof value !== "string") continue;
  Object.assign(filters, {
    [field]: field.endsWith("Id") ? Number(value) || null : value,
  });
}
productChoice.value = filters.product ?? "all";
watch(
  () => ({ ...filters }),
  (value) => {
    const query = Object.fromEntries(
      Object.entries(queryFields)
        .filter(([field]) => field !== "profileId" || activeProfileId === null)
        .map(([field, parameter]) => [
          parameter,
          value[field as keyof AnalyticsFilters] ?? undefined,
        ]),
    );
    void router.replace({ query });
  },
);

const profilesQuery = useQuery({
  queryKey: ["profiles", "analytics-options", activeProfileId ?? "overview"],
  queryFn: () =>
    activeProfileId
      ? getProfile(activeProfileId).then((profile) => [profile])
      : listProfiles(),
});
const profiles = computed(() =>
  (profilesQuery.data.value ?? []).filter(
    (profile) => activeProfileId === null || profile.id === activeProfileId,
  ),
);
const strategiesQuery = useQuery({
  queryKey: computed(() => [
    "analytics-strategies",
    profiles.value.map((item) => item.id),
  ]),
  enabled: computed(() => profiles.value.length > 0),
  queryFn: async () =>
    (
      await Promise.all(
        profiles.value.map((profile) => listStrategies(profile.id)),
      )
    ).flat(),
});
const walletsQuery = useQuery({
  queryKey: computed(() => [
    "analytics-wallets",
    profiles.value.map((item) => item.id),
  ]),
  enabled: computed(() => profiles.value.length > 0),
  queryFn: async () =>
    Promise.all(profiles.value.map((profile) => getWallet(profile.id))),
});
const strategies = computed(() => strategiesQuery.data.value ?? []);
const wallets = computed(() => walletsQuery.data.value ?? []);
const profileById = computed(
  () => new Map(profiles.value.map((item) => [item.id, item])),
);
const strategyById = computed(
  () => new Map(strategies.value.map((item) => [item.id, item])),
);
const walletAssetById = computed(
  () =>
    new Map(
      wallets.value.flatMap((wallet) =>
        wallet.assets.map((asset) => [asset.id, asset] as const),
      ),
    ),
);

const periodOptions = computed<SelectOption<AnalyticsPeriod>[]>(() =>
  (
    [
      "all_time",
      "last_30_days",
      "last_90_days",
      "year_to_date",
      "custom",
    ] as const
  ).map((value) => ({
    value,
    label: t(`analytics.period.${value}`),
  })),
);
const productOptions = computed<SelectOption<ProductChoice>[]>(() => [
  { value: "all", label: t("analytics.filters.allProducts") },
  ...(["spot", "perpetual_future", "cash_equity"] as ProductKind[]).map(
    (value) => ({
      value,
      label: t(`venues.products.${value}`),
    }),
  ),
]);
const profileOptions = computed<SearchableOption[]>(() =>
  profiles.value.map((profile) => ({
    value: profile.id,
    label: profile.name,
    detail: profile.is_archived ? t("analytics.filters.archived") : undefined,
  })),
);
const strategyOptions = computed<SearchableOption[]>(() =>
  strategies.value
    .filter(
      (strategy) =>
        filters.profileId === null || strategy.profile_id === filters.profileId,
    )
    .map((strategy) => ({
      value: strategy.id,
      label: strategy.name,
      detail: `1:${formatDecimal(String(strategy.reward_multiple))} · ${formatDecimal(
        strategy.risk_percent,
      )}%${strategy.is_archived ? ` · ${t("analytics.filters.archived")}` : ""}`,
    })),
);
const allocationOptions = computed<SearchableOption[]>(() =>
  strategies.value
    .filter(
      (strategy) =>
        (filters.profileId === null ||
          strategy.profile_id === filters.profileId) &&
        (filters.strategyId === null || strategy.id === filters.strategyId),
    )
    .flatMap((strategy) =>
      strategy.allocations.map((allocation) => {
        const asset = walletAssetById.value.get(allocation.asset_id);
        return {
          value: allocation.id,
          label: `${strategy.name} · ${formatDecimal(allocation.capital)} ${
            asset?.symbol ?? ""
          }`.trim(),
          detail: allocation.is_archived
            ? t("analytics.filters.archived")
            : undefined,
        };
      }),
    ),
);
const customDateError = computed(() => {
  if (filters.period !== "custom") return null;
  if (!filters.dateFrom && !filters.dateTo) {
    return t("analytics.filters.dateRequired");
  }
  if (filters.dateFrom && filters.dateTo && filters.dateFrom > filters.dateTo) {
    return t("analytics.filters.dateOrder");
  }
  return null;
});
const analyticsQuery = useQuery({
  queryKey: computed(() => [
    "analytics",
    activeProfileId ?? "overview",
    { ...filters },
  ]),
  enabled: computed(() => customDateError.value === null),
  queryFn: () => getAnalytics({ ...filters }, activeProfileId ?? undefined),
});
const analytics = computed(() => analyticsQuery.data.value ?? null);
const selectedMoney = computed(
  () =>
    analytics.value?.monetary.find(
      (item) => item.strategy_capital_id === selectedMoneyId.value,
    ) ?? null,
);

watch(productChoice, (value) => {
  filters.product = value === "all" ? null : value;
  filters.instrumentId = null;
});
watch(
  () => filters.profileId,
  () => {
    filters.strategyId = null;
    filters.strategyCapitalId = null;
    filters.instrumentId = null;
    filters.settlementAssetId = null;
  },
);
watch(
  () => filters.strategyId,
  () => {
    filters.strategyCapitalId = null;
  },
);
watch(
  () => analytics.value?.monetary,
  (groups) => {
    if (groups === undefined) return;
    const preferred = filters.strategyCapitalId;
    if (
      preferred !== null &&
      groups.some((item) => item.strategy_capital_id === preferred)
    ) {
      selectedMoneyId.value = preferred;
      return;
    }
    if (
      !groups.some((item) => item.strategy_capital_id === selectedMoneyId.value)
    ) {
      selectedMoneyId.value = groups[0]?.strategy_capital_id ?? null;
    }
  },
  { immediate: true },
);

function resetFilters(): void {
  Object.assign(filters, {
    period: "all_time",
    dateFrom: null,
    dateTo: null,
    profileId: activeProfileId,
    strategyId: null,
    product: null,
    instrumentId: null,
    settlementAssetId: null,
    strategyCapitalId: null,
  });
  productChoice.value = "all";
}

function signClass(value: string): string {
  const decimal = new Decimal(value);
  if (decimal.isPositive()) return "analytics-value--positive";
  if (decimal.isNegative()) return "analytics-value--negative";
  return "";
}

function ratio(value: string | null): string {
  return value === null ? "—" : formatRoundedDecimal(value, 2);
}

function percent(value: string): string {
  return `${formatRoundedDecimal(value, 2)}%`;
}

function drawdown(value: string): string {
  const formatted = ratio(value);
  return new Decimal(value).isZero() ? "0R" : `−${formatted}R`;
}

function escapeHtml(value: string): string {
  return value
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function tooltipPoint(params: unknown): ChartPoint | null {
  const values = Array.isArray(params) ? params : [params];
  for (const value of values) {
    const point = (value as TooltipParameter | undefined)?.data;
    if (point?.tradeId !== null && point?.tradeId !== undefined) return point;
  }
  return null;
}

function baseOption(): EChartsCoreOption {
  return {
    animationDuration: 420,
    animationEasing: "cubicOut",
    aria: { enabled: true },
    grid: { top: 24, right: 24, bottom: 42, left: 56 },
    textStyle: {
      color: "#84919e",
      fontFamily: "IBM Plex Sans",
    },
    xAxis: {
      axisLine: { lineStyle: { color: "#25303c" } },
      axisLabel: { color: "#84919e" },
      splitLine: { show: false },
    },
    yAxis: {
      axisLine: { show: false },
      axisLabel: { color: "#84919e" },
      splitLine: { lineStyle: { color: "rgba(104,122,140,.12)" } },
    },
  };
}

function tooltipStyle(): object {
  return {
    backgroundColor: "rgba(18,25,34,.98)",
    borderColor: "#25303c",
    borderWidth: 1,
    padding: [9, 11],
    textStyle: {
      color: "#e7edf2",
      fontFamily: "IBM Plex Sans",
      fontSize: 12,
      lineHeight: 19,
    },
  };
}

function outcomeSeries(points: ChartPoint[]): object[] {
  const outcomes = [
    ["WIN", "#35d990"],
    ["LOSS", "#f16e76"],
    ["BREAK_EVEN", "#84919e"],
  ] as const;
  return outcomes.map(([outcome, color]) => ({
    type: "scatter",
    data: points.filter((point) => point.trade?.outcome === outcome),
    symbolSize: 8,
    cursor: "pointer",
    itemStyle: { color, borderColor: "#0d1218", borderWidth: 2 },
    z: 4,
  }));
}

const overviewOption = computed<EChartsCoreOption>(() => {
  if (analytics.value === null) return {};
  const series = buildOverviewSeries(analytics.value);
  return {
    ...baseOption(),
    tooltip: {
      ...tooltipStyle(),
      trigger: "axis",
      formatter(params: unknown) {
        const point = tooltipPoint(params);
        if (point?.trade === undefined) return "";
        return [
          `<strong>#${point.trade.trade_id} · ${escapeHtml(point.trade.pair_symbol)}</strong>`,
          `${escapeHtml(t("analytics.chart.result"))}: ${escapeHtml(
            formatRoundedDecimal(point.trade.result_r, 4),
          )}R`,
          `${escapeHtml(t("analytics.chart.cumulative"))}: ${escapeHtml(
            formatRoundedDecimal(point.exactY, 4),
          )}R`,
          escapeHtml(
            new Date(point.trade.closed_at).toLocaleDateString(locale.value),
          ),
        ].join("<br>");
      },
    },
    xAxis: { ...(baseOption().xAxis as object), type: "value", min: 0 },
    yAxis: { ...(baseOption().yAxis as object), type: "value", name: "R" },
    series: [
      {
        type: "line",
        data: series.reference,
        symbol: "none",
        silent: true,
        lineStyle: { color: "#596675", type: "dashed", width: 1 },
      },
      {
        type: "line",
        data: series.trajectory,
        showSymbol: false,
        cursor: "pointer",
        lineStyle: { color: "#35d990", width: 2 },
        areaStyle: { color: "rgba(53,217,144,.08)" },
      },
      ...outcomeSeries(series.trajectory),
    ],
  };
});

const disciplineOption = computed<EChartsCoreOption>(() => {
  if (analytics.value === null) return {};
  const series = buildDisciplineSeries(analytics.value);
  return {
    ...baseOption(),
    tooltip: {
      ...tooltipStyle(),
      trigger: "item",
      formatter(params: unknown) {
        const point = tooltipPoint(params);
        if (point?.trade === undefined) return "";
        return [
          `<strong>#${point.trade.trade_id} · ${escapeHtml(point.trade.pair_symbol)}</strong>`,
          `${escapeHtml(t("analytics.discipline.lossAxis"))}: ${escapeHtml(
            formatRoundedDecimal(point.exactX, 4),
          )}`,
          `${escapeHtml(t("analytics.discipline.winAxis"))}: ${escapeHtml(
            formatRoundedDecimal(point.exactY, 4),
          )}`,
          `${escapeHtml(t("analytics.chart.result"))}: ${escapeHtml(
            formatRoundedDecimal(point.trade.result_r, 4),
          )}R`,
        ].join("<br>");
      },
    },
    xAxis: {
      ...(baseOption().xAxis as object),
      type: "value",
      min: 0,
      name: t("analytics.discipline.lossAxis"),
      nameLocation: "middle",
      nameGap: 28,
    },
    yAxis: {
      ...(baseOption().yAxis as object),
      type: "value",
      min: 0,
      name: t("analytics.discipline.winAxis"),
    },
    series: [
      {
        type: "line",
        data: series.reference,
        symbol: "none",
        silent: true,
        lineStyle: { color: "#e8b85f", type: "dashed", width: 1.5 },
      },
      {
        type: "line",
        data: series.trajectory,
        showSymbol: false,
        cursor: "pointer",
        lineStyle: { color: "#52edaa", width: 2 },
      },
      ...outcomeSeries(series.trajectory),
    ],
  };
});

const moneyOption = computed<EChartsCoreOption>(() => {
  if (selectedMoney.value === null) return {};
  const points = buildMonetarySeries(selectedMoney.value);
  const reference = [
    { value: [0, 0] },
    { value: [Math.max(points.length - 1, 1), 0] },
  ];
  return {
    ...baseOption(),
    tooltip: {
      ...tooltipStyle(),
      trigger: "axis",
      formatter(params: unknown) {
        const point = tooltipPoint(params);
        if (point === null) return "";
        return `${escapeHtml(t("analytics.money.cumulative"))}: ${escapeHtml(
          formatDecimal(point.exactY),
        )} ${escapeHtml(selectedMoney.value?.settlement_asset_symbol ?? "")}`;
      },
    },
    xAxis: { ...(baseOption().xAxis as object), type: "value", min: 0 },
    yAxis: { ...(baseOption().yAxis as object), type: "value" },
    series: [
      {
        type: "line",
        data: reference,
        symbol: "none",
        silent: true,
        lineStyle: { color: "#596675", type: "dashed", width: 1 },
      },
      {
        type: "line",
        data: points,
        symbolSize: 7,
        cursor: "pointer",
        lineStyle: { color: "#6aafff", width: 2 },
        itemStyle: { color: "#6aafff", borderColor: "#0d1218" },
        areaStyle: { color: "rgba(106,175,255,.08)" },
      },
    ],
  };
});

const reviewPercent = computed(() => {
  if (analytics.value === null || analytics.value.closed_trade_count === 0) {
    return 0;
  }
  return Math.round(
    (analytics.value.reviewed_trade_count /
      analytics.value.closed_trade_count) *
      100,
  );
});
const currentStreakLabel = computed(() => {
  const streak = analytics.value?.current_streak;
  if (streak?.outcome === null || streak?.outcome === undefined) return "—";
  return `${t(`analytics.outcome.${streak.outcome}`)} · ${streak.count}`;
});

function allocationIdentity(allocationId: number): {
  profile: string;
  strategy: string;
} {
  const strategy = strategies.value.find((item) =>
    item.allocations.some((allocation) => allocation.id === allocationId),
  );
  return {
    strategy: strategy?.name ?? `#${allocationId}`,
    profile:
      profileById.value.get(strategy?.profile_id ?? 0)?.name ??
      t("analytics.money.unknownProfile"),
  };
}

function openTrade(tradeId: number): void {
  const point = analyticsQuery.data.value?.trajectory.find(
    (item) => item.trade_id === tradeId,
  );
  if (point)
    void router.push({
      path: `/profiles/${point.profile_id}/trades/${tradeId}`,
      query: { returnTo: route.fullPath },
    });
}
</script>

<template>
  <section class="analytics-workspace">
    <div class="analytics-filterbar">
      <AppSelect
        v-model="filters.period"
        :options="periodOptions"
        :label="$t('analytics.filters.period')"
      />
      <SearchableSelect
        v-if="activeProfileId === null"
        v-model="filters.profileId"
        :options="profileOptions"
        :placeholder="$t('analytics.filters.allProfiles')"
        :empty-label="$t('analytics.filters.noProfiles')"
      />
      <SearchableSelect
        v-model="filters.strategyId"
        :options="strategyOptions"
        :placeholder="$t('analytics.filters.allStrategies')"
        :empty-label="$t('analytics.filters.noStrategies')"
      />
      <SearchableSelect
        v-model="filters.strategyCapitalId"
        :options="allocationOptions"
        :placeholder="$t('analytics.filters.allAllocations')"
        :empty-label="$t('analytics.filters.noAllocations')"
      />
      <button
        class="button button--secondary analytics-filterbar__more"
        :class="{ 'button--active': advancedOpen }"
        type="button"
        :aria-expanded="advancedOpen"
        @click="advancedOpen = !advancedOpen"
      >
        <SlidersHorizontal :size="16" aria-hidden="true" />
        {{ $t("analytics.filters.more") }}
      </button>
      <button
        class="icon-button"
        type="button"
        :aria-label="$t('analytics.filters.reset')"
        @click="resetFilters"
      >
        <RotateCcw :size="16" aria-hidden="true" />
      </button>
    </div>

    <div v-if="filters.period === 'custom'" class="analytics-datebar">
      <label class="field">
        <span>{{ $t("analytics.filters.from") }}</span>
        <input v-model="filters.dateFrom" type="date" />
      </label>
      <label class="field">
        <span>{{ $t("analytics.filters.to") }}</span>
        <input v-model="filters.dateTo" type="date" />
      </label>
      <span v-if="customDateError" class="field-error">
        {{ customDateError }}
      </span>
    </div>

    <div v-if="advancedOpen" class="analytics-advanced">
      <AppSelect
        v-model="productChoice"
        :options="productOptions"
        :label="$t('analytics.filters.product')"
      />
      <RemoteCatalogSelect
        v-model="filters.instrumentId"
        resource="instruments"
        :profile-id="filters.profileId ?? undefined"
        :disabled="!filters.profileId"
        :placeholder="$t('analytics.filters.allInstruments')"
        :empty-label="$t('analytics.filters.noInstruments')"
      />
      <RemoteCatalogSelect
        v-model="filters.settlementAssetId"
        resource="assets"
        :profile-id="filters.profileId ?? undefined"
        :disabled="!filters.profileId"
        :placeholder="$t('analytics.filters.allAssets')"
        :empty-label="$t('analytics.filters.noAssets')"
      />
    </div>

    <div class="analytics-tabs" role="tablist">
      <button
        v-for="tab in tabs"
        :key="tab"
        class="analytics-tab"
        :class="{ 'analytics-tab--active': activeTab === tab }"
        type="button"
        role="tab"
        :aria-selected="activeTab === tab"
        @click="activeTab = tab"
      >
        <Activity v-if="tab === 'overview'" :size="17" aria-hidden="true" />
        <Gauge v-else-if="tab === 'discipline'" :size="17" aria-hidden="true" />
        <Landmark v-else :size="17" aria-hidden="true" />
        {{ $t(`analytics.tabs.${tab}`) }}
      </button>
    </div>

    <LoadingState
      v-if="analyticsQuery.isPending.value && customDateError === null"
    />
    <ErrorState
      v-else-if="analyticsQuery.isError.value"
      @retry="analyticsQuery.refetch()"
    />
    <EmptyState
      v-else-if="analytics?.closed_trade_count === 0"
      :title="$t('analytics.empty.title')"
      :description="$t('analytics.empty.body')"
    >
      <button
        class="button button--primary"
        type="button"
        @click="router.push('/trades')"
      >
        {{ $t("analytics.empty.action") }}
        <ArrowRight :size="16" aria-hidden="true" />
      </button>
    </EmptyState>

    <template v-else-if="analytics !== null">
      <div v-if="analytics.excluded_trade_count > 0" class="analytics-warning">
        {{
          $t("analytics.excluded", {
            count: analytics.excluded_trade_count,
          })
        }}
      </div>

      <section v-if="activeTab === 'overview'" class="analytics-view">
        <div class="analytics-kpis">
          <article class="analytics-kpi analytics-kpi--lead">
            <span
              ><MetricHelp topic="netR" :label="$t('analytics.metrics.netR')"
            /></span>
            <strong :class="signClass(analytics.net_result_r)">
              {{ ratio(analytics.net_result_r) }}R
            </strong>
            <small>{{ $t("analytics.metrics.netRHint") }}</small>
          </article>
          <article class="analytics-kpi">
            <span
              ><MetricHelp
                topic="expectancy"
                :label="$t('analytics.metrics.expectancy')"
            /></span>
            <strong :class="signClass(analytics.expectancy_r)">
              {{ ratio(analytics.expectancy_r) }}R
            </strong>
          </article>
          <article class="analytics-kpi">
            <span
              ><MetricHelp
                topic="winRate"
                :label="$t('analytics.metrics.winRate')"
            /></span>
            <strong>{{ percent(analytics.win_rate_percent) }}</strong>
          </article>
          <article class="analytics-kpi">
            <span
              ><MetricHelp
                topic="drawdown"
                :label="$t('analytics.metrics.drawdown')"
            /></span>
            <strong class="analytics-value--negative">
              {{ drawdown(analytics.maximum_drawdown_r) }}
            </strong>
          </article>
        </div>

        <article class="analytics-panel analytics-panel--hero">
          <header class="analytics-panel__header">
            <div>
              <ChartNoAxesCombined :size="19" aria-hidden="true" />
              <div>
                <h2>
                  <MetricHelp
                    topic="trajectory"
                    :label="$t('analytics.overview.trajectory')"
                  />
                </h2>
                <p>{{ $t("analytics.overview.trajectoryHint") }}</p>
              </div>
            </div>
            <span class="analytics-panel__count">
              {{
                $t("analytics.tradeCount", {
                  count: analytics.closed_trade_count,
                })
              }}
            </span>
          </header>
          <AnalyticsChart
            :option="overviewOption"
            :label="$t('analytics.overview.chartLabel')"
            @select-trade="openTrade"
          />
        </article>

        <div class="analytics-detail-grid">
          <article class="analytics-panel analytics-review">
            <header>
              <span
                ><MetricHelp
                  topic="review"
                  :label="$t('analytics.review.title')"
              /></span>
              <strong>{{ reviewPercent }}%</strong>
            </header>
            <div class="analytics-review__track">
              <span :style="{ width: `${reviewPercent}%` }"></span>
            </div>
            <p>
              {{
                $t("analytics.review.progress", {
                  reviewed: analytics.reviewed_trade_count,
                  total: analytics.closed_trade_count,
                })
              }}
            </p>
          </article>
          <article class="analytics-panel analytics-statlist">
            <dl>
              <div>
                <dt>
                  <MetricHelp
                    topic="profitFactor"
                    :label="$t('analytics.metrics.profitFactor')"
                  />
                </dt>
                <dd>{{ ratio(analytics.profit_factor_r) }}</dd>
              </div>
              <div>
                <dt>
                  <MetricHelp
                    topic="averageR"
                    :label="$t('analytics.metrics.averageR')"
                  />
                </dt>
                <dd>{{ ratio(analytics.average_result_r) }}R</dd>
              </div>
              <div>
                <dt>
                  <MetricHelp
                    topic="averageRating"
                    :label="$t('analytics.metrics.averageRating')"
                  />
                </dt>
                <dd>{{ ratio(analytics.average_quality_rating) }}</dd>
              </div>
            </dl>
          </article>
          <article class="analytics-panel analytics-outcomes">
            <div class="analytics-outcome analytics-outcome--win">
              <span
                ><MetricHelp topic="wins" :label="$t('analytics.metrics.wins')"
              /></span>
              <strong>{{ analytics.win_count }}</strong>
            </div>
            <div class="analytics-outcome analytics-outcome--loss">
              <span
                ><MetricHelp
                  topic="losses"
                  :label="$t('analytics.metrics.losses')"
              /></span>
              <strong>{{ analytics.loss_count }}</strong>
            </div>
            <div class="analytics-outcome">
              <span
                ><MetricHelp
                  topic="breakEven"
                  :label="$t('analytics.metrics.breakEven')"
              /></span>
              <strong>{{ analytics.break_even_count }}</strong>
            </div>
          </article>
          <article class="analytics-panel analytics-statlist">
            <dl>
              <div>
                <dt>
                  <MetricHelp
                    topic="currentStreak"
                    :label="$t('analytics.metrics.currentStreak')"
                  />
                </dt>
                <dd>{{ currentStreakLabel }}</dd>
              </div>
              <div>
                <dt>
                  <MetricHelp
                    topic="bestWinStreak"
                    :label="$t('analytics.metrics.bestWinStreak')"
                  />
                </dt>
                <dd>{{ analytics.maximum_winning_streak }}</dd>
              </div>
              <div>
                <dt>
                  <MetricHelp
                    topic="worstLossStreak"
                    :label="$t('analytics.metrics.worstLossStreak')"
                  />
                </dt>
                <dd>{{ analytics.maximum_losing_streak }}</dd>
              </div>
            </dl>
          </article>
        </div>
      </section>

      <section v-else-if="activeTab === 'discipline'" class="analytics-view">
        <EmptyState
          v-if="filters.strategyCapitalId === null"
          :title="$t('analytics.discipline.selectTitle')"
          :description="$t('analytics.discipline.selectBody')"
        >
          <template #icon><Gauge :size="24" aria-hidden="true" /></template>
        </EmptyState>
        <article
          v-else-if="analytics.discipline_available"
          class="analytics-panel analytics-panel--discipline"
        >
          <header class="analytics-panel__header">
            <div>
              <Gauge :size="19" aria-hidden="true" />
              <div>
                <h2>
                  <MetricHelp
                    topic="discipline"
                    :label="$t('analytics.discipline.title')"
                  />
                </h2>
                <p>{{ $t("analytics.discipline.body") }}</p>
              </div>
            </div>
            <span class="analytics-ratio">
              1:{{
                formatDecimal(String(analytics.discipline_reward_multiple))
              }}
            </span>
          </header>
          <AnalyticsChart
            :option="disciplineOption"
            :label="$t('analytics.discipline.chartLabel')"
            @select-trade="openTrade"
          />
          <footer class="analytics-discipline-legend">
            <span
              ><i class="legend-line legend-line--path"></i
              >{{ $t("analytics.discipline.path") }}</span
            >
            <span
              ><i class="legend-line legend-line--reference"></i
              >{{ $t("analytics.discipline.reference") }}</span
            >
            <strong :class="signClass(analytics.net_result_r)">
              {{
                $t("analytics.discipline.net", {
                  value: ratio(analytics.net_result_r),
                })
              }}
            </strong>
          </footer>
        </article>
        <EmptyState
          v-else
          :title="$t('analytics.discipline.unavailableTitle')"
          :description="$t('analytics.discipline.unavailableBody')"
        />
      </section>

      <section v-else class="analytics-view analytics-money-layout">
        <aside class="analytics-money-list">
          <button
            v-for="item in analytics.monetary"
            :key="item.strategy_capital_id"
            class="analytics-money-row"
            :class="{
              'analytics-money-row--active':
                item.strategy_capital_id === selectedMoneyId,
            }"
            type="button"
            @click="selectedMoneyId = item.strategy_capital_id"
          >
            <span>
              <strong>{{
                allocationIdentity(item.strategy_capital_id).strategy
              }}</strong>
              <small>{{
                allocationIdentity(item.strategy_capital_id).profile
              }}</small>
            </span>
            <span class="analytics-money-row__capital">
              {{ formatDecimal(item.allocation_capital) }}
              {{ item.settlement_asset_symbol }}
            </span>
            <span :class="signClass(item.net_pnl)">
              {{ formatDecimal(item.net_pnl) }}
              {{ item.settlement_asset_symbol }}
            </span>
          </button>
        </aside>

        <article
          v-if="selectedMoney"
          class="analytics-panel analytics-money-detail"
        >
          <header class="analytics-panel__header">
            <div>
              <Landmark :size="19" aria-hidden="true" />
              <div>
                <h2>
                  {{
                    allocationIdentity(selectedMoney.strategy_capital_id)
                      .strategy
                  }}
                </h2>
                <p>
                  {{
                    allocationIdentity(selectedMoney.strategy_capital_id)
                      .profile
                  }}
                </p>
              </div>
            </div>
            <div>
              <MetricHelp
                topic="netMoney"
                :label="$t('analytics.money.cumulative')"
              />
              <strong :class="signClass(selectedMoney.net_pnl)">
                {{ formatDecimal(selectedMoney.net_pnl) }}
                {{ selectedMoney.settlement_asset_symbol }}
              </strong>
            </div>
          </header>
          <div class="analytics-money-metrics">
            <div>
              <span
                ><MetricHelp
                  topic="grossProfit"
                  :label="$t('analytics.money.grossProfit')"
              /></span>
              <strong class="analytics-value--positive"
                >+{{ formatDecimal(selectedMoney.gross_profit) }}
                {{ selectedMoney.settlement_asset_symbol }}</strong
              >
            </div>
            <div>
              <span
                ><MetricHelp
                  topic="grossLoss"
                  :label="$t('analytics.money.grossLoss')"
              /></span>
              <strong class="analytics-value--negative"
                >−{{ formatDecimal(selectedMoney.gross_loss) }}
                {{ selectedMoney.settlement_asset_symbol }}</strong
              >
            </div>
            <div>
              <span
                ><MetricHelp
                  topic="return"
                  :label="$t('analytics.money.return')"
              /></span>
              <strong
                :class="signClass(selectedMoney.allocation_return_percent)"
                >{{ percent(selectedMoney.allocation_return_percent) }}</strong
              >
            </div>
            <div>
              <span
                ><MetricHelp
                  topic="trades"
                  :label="$t('analytics.money.trades')"
              /></span>
              <strong>{{ selectedMoney.trade_count }}</strong>
            </div>
          </div>
          <AnalyticsChart
            :option="moneyOption"
            :label="$t('analytics.money.chartLabel')"
            @select-trade="openTrade"
          />
        </article>
      </section>
    </template>
  </section>
</template>

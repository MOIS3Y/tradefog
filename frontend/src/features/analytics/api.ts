/** Typed API access for owner-scoped trading analytics. */

import { api } from "@/api/client";
import { toApiError } from "@/api/errors";
import type { components } from "@/api/schema";

export type Analytics = components["schemas"]["AnalyticsResponse"];
export type AnalyticsPeriod = components["schemas"]["AnalyticsPeriod"];
export type ProductKind = components["schemas"]["ProductKind"];

export interface AnalyticsFilters {
  period: AnalyticsPeriod;
  dateFrom: string | null;
  dateTo: string | null;
  profileId: number | null;
  strategyId: number | null;
  product: ProductKind | null;
  instrumentId: number | null;
  pairId: number | null;
  settlementAssetId: number | null;
  strategyCapitalId: number | null;
}

/** Fetch one exact, server-calculated analytical cohort. */
export async function getAnalytics(
  filters: AnalyticsFilters,
): Promise<Analytics> {
  const custom = filters.period === "custom";
  const { data, error, response } = await api.GET("/api/v1/analytics", {
    params: {
      query: {
        period: filters.period,
        date_from: custom ? filters.dateFrom || undefined : undefined,
        date_to: custom ? filters.dateTo || undefined : undefined,
        profile_id: filters.profileId ?? undefined,
        strategy_id: filters.strategyId ?? undefined,
        product: filters.product ?? undefined,
        instrument_id: filters.instrumentId ?? undefined,
        pair_id: filters.pairId ?? undefined,
        settlement_asset_id: filters.settlementAssetId ?? undefined,
        strategy_capital_id: filters.strategyCapitalId ?? undefined,
      },
    },
  });
  if (data === undefined) throw toApiError(error, response);
  return data;
}

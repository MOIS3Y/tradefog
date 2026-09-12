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
  settlementAssetId: number | null;
  strategyCapitalId: number | null;
}

/** Fetch one exact, server-calculated analytical cohort. */
export async function getAnalytics(
  filters: AnalyticsFilters,
  profileId?: number,
): Promise<Analytics> {
  const custom = filters.period === "custom";
  const query = {
    period: filters.period,
    date_from: custom ? filters.dateFrom || undefined : undefined,
    date_to: custom ? filters.dateTo || undefined : undefined,
    profile_id: filters.profileId ?? undefined,
    strategy_id: filters.strategyId ?? undefined,
    product: filters.product ?? undefined,
    instrument_id: filters.instrumentId ?? undefined,
    settlement_asset_id: filters.settlementAssetId ?? undefined,
    strategy_capital_id: filters.strategyCapitalId ?? undefined,
  };
  const { profile_id: filter, ...scopedQuery } = query;
  const { data, error, response } =
    profileId === undefined
      ? await api.GET("/api/v1/analytics", { params: { query } })
      : await api.GET("/api/v1/profiles/{profile_id}/analytics", {
          params: { path: { profile_id: profileId }, query: scopedQuery },
        });
  if (data === undefined) throw toApiError(error, response);
  return data;
}

/** Distinguish applied restrictions from list presentation preferences. */
import type { TradeListParams } from "./api";

export function hasTradeFilters(params: TradeListParams): boolean {
  return Boolean(
    params.q?.trim() ||
    params.trade_status ||
    (params.review && params.review !== "all") ||
    params.rated !== undefined ||
    params.direction ||
    params.profile_id ||
    params.strategy_id ||
    params.date_from ||
    params.date_to,
  );
}

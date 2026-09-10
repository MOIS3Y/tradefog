/** Display precision comes from received candles, never order constraints. */
import Decimal from "decimal.js";
import type { Candle } from "./types";

export interface CandlePrecision {
  pricePrecision: number;
  volumePrecision: number;
}

/** Keep observed significant decimal places; never shrink on an update. */
export function candlePrecision(
  bars: readonly Candle[],
  previous: CandlePrecision,
): CandlePrecision {
  let { pricePrecision, volumePrecision } = previous;
  for (const bar of bars) {
    for (const value of [bar.open, bar.high, bar.low, bar.close]) {
      pricePrecision = Math.max(pricePrecision, new Decimal(value).dp());
    }
    if (bar.volume !== undefined) {
      volumePrecision = Math.max(volumePrecision, new Decimal(bar.volume).dp());
    }
  }
  // Canvas numbers use toFixed, whose supported precision ends at 100.
  return {
    pricePrecision: Math.min(pricePrecision, 100),
    volumePrecision: Math.min(volumePrecision, 100),
  };
}

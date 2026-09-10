/** Bybit presentation registration; market transport belongs to Tradefog. */
import { marketCandles, marketBook } from "./transport";
import type { MarketAdapter } from "./types";
export const bybit: MarketAdapter = {
  id: "bybit",
  name: "Bybit",
  refreshMs: 1000,
  timeframes: [
    { value: "1m", label: "1m", span: 1, unit: "minute" },
    { value: "5m", label: "5m", span: 5, unit: "minute" },
    { value: "15m", label: "15m", span: 15, unit: "minute" },
    { value: "1h", label: "1h", span: 1, unit: "hour" },
    { value: "4h", label: "4h", span: 4, unit: "hour" },
    { value: "1d", label: "1D", span: 1, unit: "day" },
    { value: "1w", label: "1W", span: 1, unit: "week" },
    { value: "1M", label: "1M", span: 1, unit: "month" },
  ],
  supports: (i) =>
    /^[A-Z0-9]+$/.test(i.symbol) &&
    (i.product === "spot" ||
      (i.product === "perpetual_future" && ["USDT", "USDC"].includes(i.quote))),
  link(i) {
    if (i.product === "spot") {
      return `https://www.bybit.com/en/trade/spot/${encodeURIComponent(i.base)}/${encodeURIComponent(i.quote)}`;
    }
    if (i.quote === "USDC") {
      return `https://www.bybit.com/en/trade/futures/usdc/${encodeURIComponent(i.base)}-PERP`;
    }
    return `https://www.bybit.com/trade/usdt/${encodeURIComponent(i.symbol)}`;
  },
  candles: (instrument, request) => marketCandles("bybit", instrument, request),
  book: (instrument, signal) => marketBook("bybit", instrument, signal),
};

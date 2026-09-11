/** Authenticated, provider-neutral market transport; no exchange payloads. */
import Decimal from "decimal.js";
import { api } from "@/api/client";
import type { components } from "@/api/schema";
import {
  MarketError,
  type MarketInstrument,
  type CandleRequest,
  type CandlePage,
  type OrderBook,
  type BookLevel,
} from "./types";

type Product = "spot" | "perpetual_future";
type Timeframe = "1m" | "5m" | "15m" | "1h" | "4h" | "1d" | "1w" | "1M";

/** Preserve server cooldowns without treating an auth failure as a ban. */
function failure(response: Response): MarketError {
  const retry = response.headers.get("Retry-After");
  const seconds = Number(retry);
  const delay =
    retry && !Number.isFinite(seconds)
      ? Math.max(0, Date.parse(retry) - Date.now())
      : seconds * 1000;
  return new MarketError(
    Math.max(delay || 0, response.status === 429 ? 60_000 : 0),
  );
}

/** Cumulative volume is a display calculation, not journal accounting. */
export function cumulativeLevels(
  levels: components["schemas"]["BookLevel"][],
): BookLevel[] {
  const Exact = Decimal.clone({ precision: 96 });
  let total = new Exact(0);
  return levels.map((level) => {
    total = total.plus(level.size);
    return { ...level, total: total.toFixed() };
  });
}

export async function marketCandles(
  venue: string,
  instrument: MarketInstrument,
  request: CandleRequest,
): Promise<CandlePage> {
  const { data, response } = await api.GET(
    "/api/v1/venues/{venue_type}/public/klines",
    {
      params: {
        path: { venue_type: venue },
        query: {
          symbol: instrument.symbol,
          product: instrument.product as Product,
          timeframe: request.timeframe as Timeframe,
          before: request.before,
          limit: request.limit ?? 500,
        },
      },
      signal: AbortSignal.any([request.signal, AbortSignal.timeout(15_000)]),
    },
  );
  if (data === undefined) throw failure(response);
  return {
    bars: data.bars.map((bar) => ({
      ...bar,
      turnover: bar.turnover ?? undefined,
    })),
    hasMore: data.has_more,
  };
}

export async function marketBook(
  venue: string,
  instrument: MarketInstrument,
  signal: AbortSignal,
): Promise<OrderBook> {
  const { data, response } = await api.GET(
    "/api/v1/venues/{venue_type}/public/orderbook",
    {
      params: {
        path: { venue_type: venue },
        query: {
          symbol: instrument.symbol,
          product: instrument.product as Product,
          limit: 50,
        },
      },
      signal: AbortSignal.any([signal, AbortSignal.timeout(15_000)]),
    },
  );
  if (data === undefined) throw failure(response);
  return {
    timestamp: data.timestamp,
    bids: cumulativeLevels(data.bids),
    asks: cumulativeLevels(data.asks),
  };
}

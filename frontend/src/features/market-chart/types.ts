/** Provider-neutral public market contracts; money stays decimal text. */
export interface MarketInstrument {
  symbol: string;
  product: string;
  base: string;
  quote: string;
}

export interface Candle {
  timestamp: number;
  open: string;
  high: string;
  low: string;
  close: string;
  volume?: string;
  turnover?: string;
}

export interface BookLevel {
  price: string;
  size: string;
  total: string;
}

export interface OrderBook {
  timestamp: number;
  bids: BookLevel[];
  asks: BookLevel[];
}

export interface Timeframe {
  value: string;
  label: string;
  span: number;
  unit: "minute" | "hour" | "day" | "week" | "month";
}

export interface CandleRequest {
  timeframe: string;
  before?: number;
  limit?: number;
  signal: AbortSignal;
}

export interface CandlePage {
  bars: Candle[];
  hasMore: boolean;
}

export interface MarketAdapter {
  id: string;
  name: string;
  refreshMs: number;
  timeframes: Timeframe[];
  supports: (instrument: MarketInstrument) => boolean;
  link: (instrument: MarketInstrument) => string;
  candles?: (
    instrument: MarketInstrument,
    request: CandleRequest,
  ) => Promise<CandlePage>;
  book?: (
    instrument: MarketInstrument,
    signal: AbortSignal,
  ) => Promise<OrderBook>;
}

/** A provider cooldown must survive local retries and timeframe changes. */
export class MarketError extends Error {
  constructor(public readonly retryAfterMs = 0) {
    super("Public market data unavailable");
  }
}

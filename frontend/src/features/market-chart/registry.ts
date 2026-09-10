/** Register optional market presentations without coupling the position form. */
import { bybit } from "./bybit";
import type { MarketAdapter, MarketInstrument } from "./types";

const adapters: MarketAdapter[] = [bybit];

/** Manual profiles never create a market feed. */
export function resolveMarket(
  provider: string | undefined,
  instrument: MarketInstrument | undefined,
): MarketAdapter | undefined {
  return instrument
    ? adapters.find(
        (adapter) =>
          adapter.id === provider &&
          adapter.supports(instrument) &&
          (adapter.candles || adapter.book),
      )
    : undefined;
}

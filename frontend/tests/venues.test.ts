import { beforeEach, describe, expect, it, vi } from "vitest";

import { reloadTokens } from "@/api/tokens";
import type { Asset, Pair } from "@/features/catalog/api";
import {
  createInstrument,
  createVenue,
  createVenueWalletAsset,
  deleteInstrument,
  deleteVenue,
  deleteVenueWalletAsset,
  updateVenueWalletAsset,
  type Instrument,
  type Venue,
  type VenueWalletAsset,
} from "@/features/venues/api";
import {
  filterInstruments,
  filterVenues,
  filterWalletAssets,
  sortInstruments,
} from "@/features/venues/filters";
import { formatDecimal } from "@/utils/decimal";

const bitcoin: Asset = {
  id: 1,
  symbol: "BTC",
  name: "Bitcoin",
  asset_type: "crypto",
};
const dollar: Asset = {
  id: 2,
  symbol: "USD",
  name: "US Dollar",
  asset_type: "fiat",
};
const pair: Pair = {
  id: 3,
  base: bitcoin,
  quote: dollar,
  canonical_symbol: "BTC/USD",
};
const venue: Venue = {
  id: 4,
  name: "Bybit",
  market_data_provider: "bybit",
  description: "Crypto exchange",
  website: "https://bybit.com",
  is_active: true,
};
const archivedVenue: Venue = {
  ...venue,
  id: 5,
  name: "Paper broker",
  market_data_provider: "none",
  description: "Simulation account",
  website: null,
  is_active: false,
};
const instrument: Instrument = {
  id: 6,
  venue_id: venue.id,
  pair,
  product: "perpetual_future",
  exec_symbol: "BTCUSD",
  price_step: "0.01",
  qty_step: "0.001",
  min_qty: null,
  min_notional: null,
  settlement_asset: dollar,
  is_active: true,
};
const capability: VenueWalletAsset = {
  id: 7,
  venue_id: venue.id,
  asset: dollar,
  is_active: true,
};

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

beforeEach(() => {
  window.localStorage.clear();
  reloadTokens();
  vi.unstubAllGlobals();
});

describe("venue catalog flow", () => {
  it("filters archives and sorts venue-scoped records locally", () => {
    expect(filterVenues([venue, archivedVenue], "byb", "all")).toEqual([venue]);
    expect(filterVenues([venue, archivedVenue], "", "archived")).toEqual([
      archivedVenue,
    ]);
    expect(filterInstruments([instrument], "BTC/USD", "active")).toEqual([
      instrument,
    ]);
    expect(sortInstruments([instrument], "settlement", "desc")).toEqual([
      instrument,
    ]);
    expect(filterWalletAssets([capability], "fiat", "active")).toEqual([
      capability,
    ]);
  });

  it("formats exact decimals without insignificant zeroes", () => {
    expect(formatDecimal("0.010000000000000000")).toBe("0.01");
    expect(formatDecimal("0.000001000000000000")).toBe("0.000001");
    expect(formatDecimal("10.000000000000000000")).toBe("10");
    expect(formatDecimal("12345678901234567890.0100")).toBe(
      "12345678901234567890.01",
    );
  });

  it("creates and updates the venue execution configuration", async () => {
    const archivedCapability = { ...capability, is_active: false };
    const responses = [
      jsonResponse(venue, 201),
      jsonResponse(instrument, 201),
      jsonResponse(capability, 201),
      jsonResponse(archivedCapability),
      new Response(null, { status: 204 }),
      new Response(null, { status: 204 }),
      new Response(null, { status: 204 }),
    ];
    const requests: Request[] = [];
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL) => {
        requests.push(input as Request);
        return responses.shift() as Response;
      }),
    );

    await createVenue({
      name: "Bybit",
      market_data_provider: "bybit",
      description: null,
      website: null,
      is_active: true,
    });
    await createInstrument(venue.id, {
      pair_id: pair.id,
      product: "perpetual_future",
      exec_symbol: "BTCUSD",
      price_step: "0.01",
      qty_step: "0.001",
      settlement_asset_id: dollar.id,
      is_active: true,
    });
    await createVenueWalletAsset(venue.id, dollar.id);
    await updateVenueWalletAsset(capability.id, false);
    await deleteInstrument(instrument.id);
    await deleteVenueWalletAsset(capability.id);
    await deleteVenue(archivedVenue.id);

    expect(requests.map((request) => request.method)).toEqual([
      "POST",
      "POST",
      "POST",
      "PATCH",
      "DELETE",
      "DELETE",
      "DELETE",
    ]);
    expect(new URL(requests[1]?.url ?? "").pathname).toBe(
      `/api/v1/catalog/venues/${venue.id}/instruments`,
    );
    expect(new URL(requests[2]?.url ?? "").pathname).toBe(
      `/api/v1/catalog/venues/${venue.id}/wallet-assets`,
    );
  });
});

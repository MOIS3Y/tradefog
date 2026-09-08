/** Typed API access for venues and their executable capabilities. */

import { api } from "@/api/client";
import { toApiError } from "@/api/errors";
import type { components } from "@/api/schema";

export type Venue = components["schemas"]["VenueResponse"];
export type VenueWrite = components["schemas"]["VenueWrite"];
export type MarketDataProvider = components["schemas"]["MarketDataProvider"];
export type Instrument = components["schemas"]["InstrumentResponse"];
export type InstrumentWrite = components["schemas"]["InstrumentWrite"];
export type ProductKind = components["schemas"]["ProductKind"];
export type VenueWalletAsset =
  components["schemas"]["VenueWalletAssetResponse"];

export async function listVenues(): Promise<Venue[]> {
  const { data, error, response } = await api.GET("/api/v1/catalog/venues", {
    params: { query: { active_only: false } },
  });
  if (data === undefined) {
    throw toApiError(error, response);
  }
  return data;
}

export async function createVenue(input: VenueWrite): Promise<Venue> {
  const { data, error, response } = await api.POST("/api/v1/catalog/venues", {
    body: input,
  });
  if (data === undefined) {
    throw toApiError(error, response);
  }
  return data;
}

export async function updateVenue(
  id: number,
  input: components["schemas"]["VenuePatch"],
): Promise<Venue> {
  const { data, error, response } = await api.PATCH(
    "/api/v1/catalog/venues/{venue_id}",
    { params: { path: { venue_id: id } }, body: input },
  );
  if (data === undefined) {
    throw toApiError(error, response);
  }
  return data;
}

export async function deleteVenue(id: number): Promise<void> {
  const { error, response } = await api.DELETE(
    "/api/v1/catalog/venues/{venue_id}",
    { params: { path: { venue_id: id } } },
  );
  if (!response.ok) {
    throw toApiError(error, response);
  }
}

export async function listInstruments(venueId: number): Promise<Instrument[]> {
  const { data, error, response } = await api.GET(
    "/api/v1/catalog/venues/{venue_id}/instruments",
    {
      params: {
        path: { venue_id: venueId },
        query: { active_only: false },
      },
    },
  );
  if (data === undefined) {
    throw toApiError(error, response);
  }
  return data;
}

export async function createInstrument(
  venueId: number,
  input: InstrumentWrite,
): Promise<Instrument> {
  const { data, error, response } = await api.POST(
    "/api/v1/catalog/venues/{venue_id}/instruments",
    { params: { path: { venue_id: venueId } }, body: input },
  );
  if (data === undefined) {
    throw toApiError(error, response);
  }
  return data;
}

export async function updateInstrument(
  id: number,
  input: components["schemas"]["InstrumentPatch"],
): Promise<Instrument> {
  const { data, error, response } = await api.PATCH(
    "/api/v1/catalog/instruments/{instrument_id}",
    { params: { path: { instrument_id: id } }, body: input },
  );
  if (data === undefined) {
    throw toApiError(error, response);
  }
  return data;
}

export async function deleteInstrument(id: number): Promise<void> {
  const { error, response } = await api.DELETE(
    "/api/v1/catalog/instruments/{instrument_id}",
    { params: { path: { instrument_id: id } } },
  );
  if (!response.ok) {
    throw toApiError(error, response);
  }
}

export async function listVenueWalletAssets(
  venueId: number,
): Promise<VenueWalletAsset[]> {
  const { data, error, response } = await api.GET(
    "/api/v1/catalog/venues/{venue_id}/wallet-assets",
    {
      params: {
        path: { venue_id: venueId },
        query: { active_only: false },
      },
    },
  );
  if (data === undefined) {
    throw toApiError(error, response);
  }
  return data;
}

export async function createVenueWalletAsset(
  venueId: number,
  assetId: number,
): Promise<VenueWalletAsset> {
  const { data, error, response } = await api.POST(
    "/api/v1/catalog/venues/{venue_id}/wallet-assets",
    {
      params: { path: { venue_id: venueId } },
      body: { asset_id: assetId, is_active: true },
    },
  );
  if (data === undefined) {
    throw toApiError(error, response);
  }
  return data;
}

export async function updateVenueWalletAsset(
  id: number,
  isActive: boolean,
): Promise<VenueWalletAsset> {
  const { data, error, response } = await api.PATCH(
    "/api/v1/catalog/wallet-assets/{venue_wallet_asset_id}",
    {
      params: { path: { venue_wallet_asset_id: id } },
      body: { is_active: isActive },
    },
  );
  if (data === undefined) {
    throw toApiError(error, response);
  }
  return data;
}

export async function deleteVenueWalletAsset(id: number): Promise<void> {
  const { error, response } = await api.DELETE(
    "/api/v1/catalog/wallet-assets/{venue_wallet_asset_id}",
    { params: { path: { venue_wallet_asset_id: id } } },
  );
  if (!response.ok) {
    throw toApiError(error, response);
  }
}

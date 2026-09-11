/** Profile-owned market setup; no funding or private exchange access. */
import { api } from "@/api/client";
import { toApiError } from "@/api/errors";
import type { components } from "@/api/schema";
import type { ListParams, Page } from "@/api/pagination";

export type Asset = components["schemas"]["AssetResponse"];
export type Instrument = components["schemas"]["InstrumentResponse"];
export type Venue = components["schemas"]["VenueCapabilities"];
export type InstrumentSpec = components["schemas"]["InstrumentSpec"];
export type VenueType = components["schemas"]["VenueType"];

/** Read integration choices without importing instruments. */
export async function listVenues(): Promise<Venue[]> {
  const { data, error, response } = await api.GET("/api/v1/venues");
  if (data === undefined) throw toApiError(error, response);
  return data;
}

/** Page the profile-owned asset catalog. */
export async function listAssets(
  profileId: number,
  query: ListParams & {
    hide_empty?: boolean;
    asset_type?: Asset["asset_type"];
  } = {},
): Promise<Page<Asset>> {
  const { data, error, response } = await api.GET(
    "/api/v1/profiles/{profile_id}/assets",
    { params: { path: { profile_id: profileId }, query } },
  );
  if (data === undefined) throw toApiError(error, response);
  return data;
}
/** Resolve one asset independently of the current options page. */
export async function getAsset(profileId: number, id: number): Promise<Asset> {
  const { data, error, response } = await api.GET(
    "/api/v1/profiles/{profile_id}/assets/{asset_id}",
    { params: { path: { profile_id: profileId, asset_id: id } } },
  );
  if (data === undefined) throw toApiError(error, response);
  return data;
}
/** Create a manual profile asset, never a wallet balance. */
export async function createAsset(
  profileId: number,
  input: components["schemas"]["AssetWrite"],
): Promise<Asset> {
  const { data, error, response } = await api.POST(
    "/api/v1/profiles/{profile_id}/assets",
    { params: { path: { profile_id: profileId } }, body: input },
  );
  if (data === undefined) throw toApiError(error, response);
  return data;
}
/** Change presentation or availability without changing identity. */
export async function updateAsset(
  profileId: number,
  id: number,
  input: components["schemas"]["AssetPatch"],
): Promise<Asset> {
  const { data, error, response } = await api.PATCH(
    "/api/v1/profiles/{profile_id}/assets/{asset_id}",
    { params: { path: { profile_id: profileId, asset_id: id } }, body: input },
  );
  if (data === undefined) throw toApiError(error, response);
  return data;
}
/** Request deletion of an inactive, unreferenced profile asset. */
export async function deleteAsset(
  profileId: number,
  id: number,
): Promise<void> {
  const { error, response } = await api.DELETE(
    "/api/v1/profiles/{profile_id}/assets/{asset_id}",
    { params: { path: { profile_id: profileId, asset_id: id } } },
  );
  if (!response.ok) throw toApiError(error, response);
}

/** Page only the instruments selected for this profile. */
export async function listInstruments(
  profileId: number,
  query: ListParams & { product?: Instrument["product"] } = {},
): Promise<Page<Instrument>> {
  const { data, error, response } = await api.GET(
    "/api/v1/profiles/{profile_id}/instruments",
    { params: { path: { profile_id: profileId }, query } },
  );
  if (data === undefined) throw toApiError(error, response);
  return data;
}
/** Resolve instrument identity within its owning profile. */
export async function getInstrument(
  profileId: number,
  id: number,
): Promise<Instrument> {
  const { data, error, response } = await api.GET(
    "/api/v1/profiles/{profile_id}/instruments/{instrument_id}",
    { params: { path: { profile_id: profileId, instrument_id: id } } },
  );
  if (data === undefined) throw toApiError(error, response);
  return data;
}
/** Import a symbol or create a complete manual specification. */
export async function createInstrument(
  profileId: number,
  input:
    | components["schemas"]["ManualInstrumentWrite"]
    | components["schemas"]["BybitInstrumentWrite"],
): Promise<Instrument> {
  const { data, error, response } = await api.POST(
    "/api/v1/profiles/{profile_id}/instruments",
    { params: { path: { profile_id: profileId } }, body: input },
  );
  if (data === undefined) throw toApiError(error, response);
  return data;
}
/** Update editable rules while preserving instrument identity. */
export async function updateInstrument(
  profileId: number,
  id: number,
  input: components["schemas"]["InstrumentPatch"],
): Promise<Instrument> {
  const { data, error, response } = await api.PATCH(
    "/api/v1/profiles/{profile_id}/instruments/{instrument_id}",
    {
      params: { path: { profile_id: profileId, instrument_id: id } },
      body: input,
    },
  );
  if (data === undefined) throw toApiError(error, response);
  return data;
}
/** Request deletion of an archived, unreferenced instrument. */
export async function deleteInstrument(
  profileId: number,
  id: number,
): Promise<void> {
  const { error, response } = await api.DELETE(
    "/api/v1/profiles/{profile_id}/instruments/{instrument_id}",
    { params: { path: { profile_id: profileId, instrument_id: id } } },
  );
  if (!response.ok) throw toApiError(error, response);
}

/** Refresh exchange rules without implicitly unarchiving an instrument. */
export async function refreshInstrument(
  profileId: number,
  id: number,
): Promise<Instrument> {
  const { data, error, response } = await api.POST(
    "/api/v1/profiles/{profile_id}/instruments/{instrument_id}/refresh",
    { params: { path: { profile_id: profileId, instrument_id: id } } },
  );
  if (data === undefined) throw toApiError(error, response);
  return data;
}
/** Browse provider metadata without importing or funding anything. */
export async function searchExchange(
  venueType: string,
  product: "spot" | "perpetual_future",
  symbol?: string,
  cursor?: string,
): Promise<components["schemas"]["InstrumentPage"]> {
  const { data, error, response } = await api.GET(
    "/api/v1/venues/{venue_type}/public/instruments",
    {
      params: {
        path: { venue_type: venueType },
        query: { product, q: symbol || undefined, cursor },
      },
    },
  );
  if (data === undefined) throw toApiError(error, response);
  return data;
}

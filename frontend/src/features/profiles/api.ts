/** Typed API access for owner-scoped profiles, wallets, and strategies. */

import { listAssets, type Asset } from "./marketApi";
import { api } from "@/api/client";
import { toApiError } from "@/api/errors";
import type { components } from "@/api/schema";
import type { ListParams, Page } from "@/api/pagination";

export type Profile = components["schemas"]["ProfileResponse"];
export type ProfileCreate = components["schemas"]["ProfileCreate"];
export type ProfilePatch = components["schemas"]["ProfilePatch"];
export interface Wallet {
  assets: Asset[];
}
export type WalletOperation = components["schemas"]["WalletOperationResponse"];
export type WalletOperationKind = components["schemas"]["WalletOperationKind"];
export type Strategy = components["schemas"]["StrategyResponse"];
export type StrategyCreate = components["schemas"]["StrategyCreate"];
export type StrategyPatch = components["schemas"]["StrategyPatch"];
export type Allocation = components["schemas"]["StrategyCapitalResponse"];

export async function listProfilePage(
  params: ListParams = {},
): Promise<Page<Profile>> {
  const { data, error, response } = await api.GET("/api/v1/profiles", {
    params: { query: params },
  });
  if (data === undefined) throw toApiError(error, response);
  return data;
}

/** Load complete options for existing profile selectors, in bounded pages. */
export async function listProfiles(): Promise<Profile[]> {
  const profiles: Profile[] = [];
  let page = 1;
  while (true) {
    const result = await listProfilePage({ page, page_size: 100 });
    profiles.push(...result.items);
    if (profiles.length >= result.total || result.items.length === 0) {
      return profiles;
    }
    page += 1;
  }
}

export async function getProfile(id: number): Promise<Profile> {
  const { data, error, response } = await api.GET(
    "/api/v1/profiles/{profile_id}",
    { params: { path: { profile_id: id } } },
  );
  if (data === undefined) throw toApiError(error, response);
  return data;
}

export async function createProfile(input: ProfileCreate): Promise<Profile> {
  const { data, error, response } = await api.POST("/api/v1/profiles", {
    body: input,
  });
  if (data === undefined) throw toApiError(error, response);
  return data;
}

export async function updateProfile(
  id: number,
  input: ProfilePatch,
): Promise<Profile> {
  const { data, error, response } = await api.PATCH(
    "/api/v1/profiles/{profile_id}",
    { params: { path: { profile_id: id } }, body: input },
  );
  if (data === undefined) throw toApiError(error, response);
  return data;
}

export async function deleteProfile(id: number): Promise<void> {
  const { error, response } = await api.DELETE(
    "/api/v1/profiles/{profile_id}",
    { params: { path: { profile_id: id } } },
  );
  if (!response.ok) throw toApiError(error, response);
}

export async function getWallet(profileId: number): Promise<Wallet> {
  const assets: Asset[] = [];
  for (let page = 1; ; page++) {
    const result = await listAssets(profileId, {
      page,
      page_size: 100,
      visibility: "all",
    });
    assets.push(...result.items);
    if (assets.length >= result.total || !result.items.length) break;
  }
  return { assets };
}

export type ProfileOperation =
  components["schemas"]["ProfileOperationResponse"];
export type OperationFilters = ListParams & {
  asset_id?: number;
  kind?: WalletOperationKind;
  date_from?: string;
  date_to?: string;
  sort?: "created_at" | "kind";
};
export async function listProfileOperations(
  profileId: number,
  query: OperationFilters = {},
): Promise<Page<ProfileOperation>> {
  const { data, error, response } = await api.GET(
    "/api/v1/profiles/{profile_id}/operations",
    { params: { path: { profile_id: profileId }, query } },
  );
  if (data === undefined) throw toApiError(error, response);
  return data;
}

export async function listOperations(
  profileId: number,
  assetId: number,
  query: { page?: number; page_size?: number } = {},
): Promise<Page<WalletOperation>> {
  const { data, error, response } = await api.GET(
    "/api/v1/profiles/{profile_id}/assets/{asset_id}/operations",
    { params: { path: { profile_id: profileId, asset_id: assetId }, query } },
  );
  if (data === undefined) throw toApiError(error, response);
  return data;
}

export async function createOperation(
  profileId: number,
  assetId: number,
  input: components["schemas"]["WalletOperationCreate"],
): Promise<WalletOperation> {
  const { data, error, response } = await api.POST(
    "/api/v1/profiles/{profile_id}/assets/{asset_id}/operations",
    {
      params: { path: { profile_id: profileId, asset_id: assetId } },
      body: input,
    },
  );
  if (data === undefined) throw toApiError(error, response);
  return data;
}

export async function updateOperationNote(
  profileId: number,
  assetId: number,
  id: number,
  note: string | null,
): Promise<WalletOperation> {
  const { data, error, response } = await api.PATCH(
    "/api/v1/profiles/{profile_id}/assets/{asset_id}/operations/{operation_id}",
    {
      params: {
        path: { profile_id: profileId, asset_id: assetId, operation_id: id },
      },
      body: { note },
    },
  );
  if (data === undefined) throw toApiError(error, response);
  return data;
}

export async function listStrategies(profileId: number): Promise<Strategy[]> {
  const items: Strategy[] = [];
  let page = 1;
  for (;;) {
    const { data, error, response } = await api.GET(
      "/api/v1/profiles/{profile_id}/strategies",
      {
        params: {
          path: { profile_id: profileId },
          query: { page, page_size: 100, visibility: "all" },
        },
      },
    );
    if (data === undefined) throw toApiError(error, response);
    items.push(...data.items);
    if (items.length >= data.total || !data.items.length) return items;
    page++;
  }
}

export async function createStrategy(
  profileId: number,
  input: StrategyCreate,
): Promise<Strategy> {
  const { data, error, response } = await api.POST(
    "/api/v1/profiles/{profile_id}/strategies",
    { params: { path: { profile_id: profileId } }, body: input },
  );
  if (data === undefined) throw toApiError(error, response);
  return data;
}

export async function updateStrategy(
  profileId: number,
  id: number,
  input: StrategyPatch,
): Promise<Strategy> {
  const { data, error, response } = await api.PATCH(
    "/api/v1/profiles/{profile_id}/strategies/{strategy_id}",
    {
      params: { path: { profile_id: profileId, strategy_id: id } },
      body: input,
    },
  );
  if (data === undefined) throw toApiError(error, response);
  return data;
}

export async function deleteStrategy(
  profileId: number,
  id: number,
): Promise<void> {
  const { error, response } = await api.DELETE(
    "/api/v1/profiles/{profile_id}/strategies/{strategy_id}",
    { params: { path: { profile_id: profileId, strategy_id: id } } },
  );
  if (!response.ok) throw toApiError(error, response);
}

export async function createAllocation(
  profileId: number,
  strategyId: number,
  walletAssetId: number,
  capital: string,
): Promise<Allocation> {
  const { data, error, response } = await api.POST(
    "/api/v1/profiles/{profile_id}/strategies/{strategy_id}/allocations",
    {
      params: { path: { profile_id: profileId, strategy_id: strategyId } },
      body: { asset_id: walletAssetId, capital },
    },
  );
  if (data === undefined) throw toApiError(error, response);
  return data;
}

export async function updateAllocation(
  profileId: number,
  strategyId: number,
  id: number,
  input: components["schemas"]["StrategyCapitalPatch"],
): Promise<Allocation> {
  const { data, error, response } = await api.PATCH(
    "/api/v1/profiles/{profile_id}/strategies/{strategy_id}/allocations/{allocation_id}",
    {
      params: {
        path: {
          profile_id: profileId,
          strategy_id: strategyId,
          allocation_id: id,
        },
      },
      body: input,
    },
  );
  if (data === undefined) throw toApiError(error, response);
  return data;
}

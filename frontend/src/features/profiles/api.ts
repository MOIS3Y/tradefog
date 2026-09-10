/** Typed API access for owner-scoped profiles, wallets, and strategies. */

import { api } from "@/api/client";
import { toApiError } from "@/api/errors";
import type { components } from "@/api/schema";
import type { ListParams, Page } from "@/api/pagination";

export type Profile = components["schemas"]["ProfileResponse"];
export type ProfileCreate = components["schemas"]["ProfileCreate"];
export type ProfilePatch = components["schemas"]["ProfilePatch"];
export type Wallet = components["schemas"]["WalletResponse"];
export type WalletAsset = components["schemas"]["WalletAssetResponse"];
export type WalletAssetCreate = components["schemas"]["WalletAssetCreate"];
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
  const { data, error, response } = await api.GET(
    "/api/v1/profiles/{profile_id}/wallet",
    {
      params: {
        path: { profile_id: profileId },
        query: { include_archived: true },
      },
    },
  );
  if (data === undefined) throw toApiError(error, response);
  return data;
}

export async function createWalletAsset(
  profileId: number,
  input: WalletAssetCreate,
): Promise<WalletAsset> {
  const { data, error, response } = await api.POST(
    "/api/v1/profiles/{profile_id}/wallet/assets",
    { params: { path: { profile_id: profileId } }, body: input },
  );
  if (data === undefined) throw toApiError(error, response);
  return data;
}

export async function updateWalletAsset(
  profileId: number,
  id: number,
  input: components["schemas"]["WalletAssetPatch"],
): Promise<WalletAsset> {
  const { data, error, response } = await api.PATCH(
    "/api/v1/profiles/{profile_id}/wallet/assets/{wallet_asset_id}",
    {
      params: { path: { profile_id: profileId, wallet_asset_id: id } },
      body: input,
    },
  );
  if (data === undefined) throw toApiError(error, response);
  return data;
}

export async function listOperations(
  profileId: number,
  query: { page?: number; page_size?: number } = {},
): Promise<Page<WalletOperation>> {
  const { data, error, response } = await api.GET(
    "/api/v1/profiles/{profile_id}/wallet/operations",
    { params: { path: { profile_id: profileId }, query } },
  );
  if (data === undefined) throw toApiError(error, response);
  return data;
}

export async function createOperation(
  profileId: number,
  input: components["schemas"]["WalletOperationCreate"],
): Promise<WalletOperation> {
  const { data, error, response } = await api.POST(
    "/api/v1/profiles/{profile_id}/wallet/operations",
    { params: { path: { profile_id: profileId } }, body: input },
  );
  if (data === undefined) throw toApiError(error, response);
  return data;
}

export async function updateOperationNote(
  profileId: number,
  id: number,
  note: string | null,
): Promise<WalletOperation> {
  const { data, error, response } = await api.PATCH(
    "/api/v1/profiles/{profile_id}/wallet/operations/{operation_id}",
    {
      params: { path: { profile_id: profileId, operation_id: id } },
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
      body: { wallet_asset_id: walletAssetId, capital },
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

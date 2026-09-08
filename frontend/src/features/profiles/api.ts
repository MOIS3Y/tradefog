/** Typed API access for owner-scoped profiles, wallets, and strategies. */

import { api } from "@/api/client";
import { toApiError } from "@/api/errors";
import type { components } from "@/api/schema";

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

export async function listProfiles(): Promise<Profile[]> {
  const { data, error, response } = await api.GET("/api/v1/profiles", {
    params: { query: { include_archived: true } },
  });
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
  id: number,
  input: components["schemas"]["WalletAssetPatch"],
): Promise<WalletAsset> {
  const { data, error, response } = await api.PATCH(
    "/api/v1/profiles/wallet-assets/{wallet_asset_id}",
    { params: { path: { wallet_asset_id: id } }, body: input },
  );
  if (data === undefined) throw toApiError(error, response);
  return data;
}

export async function listOperations(id: number): Promise<WalletOperation[]> {
  const { data, error, response } = await api.GET(
    "/api/v1/profiles/wallet-assets/{wallet_asset_id}/operations",
    { params: { path: { wallet_asset_id: id } } },
  );
  if (data === undefined) throw toApiError(error, response);
  return data;
}

export async function createOperation(
  id: number,
  input: components["schemas"]["WalletOperationCreate"],
): Promise<WalletOperation> {
  const { data, error, response } = await api.POST(
    "/api/v1/profiles/wallet-assets/{wallet_asset_id}/operations",
    { params: { path: { wallet_asset_id: id } }, body: input },
  );
  if (data === undefined) throw toApiError(error, response);
  return data;
}

export async function updateOperationNote(
  id: number,
  note: string | null,
): Promise<WalletOperation> {
  const { data, error, response } = await api.PATCH(
    "/api/v1/profiles/wallet-operations/{operation_id}",
    { params: { path: { operation_id: id } }, body: { note } },
  );
  if (data === undefined) throw toApiError(error, response);
  return data;
}

export async function listStrategies(profileId: number): Promise<Strategy[]> {
  const { data, error, response } = await api.GET(
    "/api/v1/profiles/{profile_id}/strategies",
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
  id: number,
  input: StrategyPatch,
): Promise<Strategy> {
  const { data, error, response } = await api.PATCH(
    "/api/v1/profiles/strategies/{strategy_id}",
    { params: { path: { strategy_id: id } }, body: input },
  );
  if (data === undefined) throw toApiError(error, response);
  return data;
}

export async function deleteStrategy(id: number): Promise<void> {
  const { error, response } = await api.DELETE(
    "/api/v1/profiles/strategies/{strategy_id}",
    { params: { path: { strategy_id: id } } },
  );
  if (!response.ok) throw toApiError(error, response);
}

export async function createAllocation(
  strategyId: number,
  walletAssetId: number,
  capital: string,
): Promise<Allocation> {
  const { data, error, response } = await api.POST(
    "/api/v1/profiles/strategies/{strategy_id}/allocations",
    {
      params: { path: { strategy_id: strategyId } },
      body: { wallet_asset_id: walletAssetId, capital },
    },
  );
  if (data === undefined) throw toApiError(error, response);
  return data;
}

export async function updateAllocation(
  id: number,
  input: components["schemas"]["StrategyCapitalPatch"],
): Promise<Allocation> {
  const { data, error, response } = await api.PATCH(
    "/api/v1/profiles/allocations/{allocation_id}",
    { params: { path: { allocation_id: id } }, body: input },
  );
  if (data === undefined) throw toApiError(error, response);
  return data;
}

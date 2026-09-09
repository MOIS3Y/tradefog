import { api } from "@/api/client";
import { toApiError } from "@/api/errors";
import type { components } from "@/api/schema";
import type { ListParams, Page } from "@/api/pagination";

export type Asset = components["schemas"]["AssetResponse"];
export type AssetType = components["schemas"]["AssetType"];
export type AssetWrite = components["schemas"]["AssetWrite"];
export type Pair = components["schemas"]["PairResponse"];
export type PairWrite = components["schemas"]["PairWrite"];

export async function listAssets(query: ListParams = {}): Promise<Page<Asset>> {
  const { data, error, response } = await api.GET("/api/v1/catalog/assets", {
    params: { query },
  });
  if (data === undefined) {
    throw toApiError(error, response);
  }
  return data;
}

export async function listPairs(query: ListParams = {}): Promise<Page<Pair>> {
  const { data, error, response } = await api.GET("/api/v1/catalog/pairs", {
    params: { query },
  });
  if (data === undefined) {
    throw toApiError(error, response);
  }
  return data;
}

export async function createAsset(input: AssetWrite): Promise<Asset> {
  const { data, error, response } = await api.POST("/api/v1/catalog/assets", {
    body: input,
  });
  if (data === undefined) {
    throw toApiError(error, response);
  }
  return data;
}

export async function updateAsset(
  id: number,
  input: AssetWrite,
): Promise<Asset> {
  const { data, error, response } = await api.PATCH(
    "/api/v1/catalog/assets/{asset_id}",
    { params: { path: { asset_id: id } }, body: input },
  );
  if (data === undefined) {
    throw toApiError(error, response);
  }
  return data;
}

export async function deleteAsset(id: number): Promise<void> {
  const { error, response } = await api.DELETE(
    "/api/v1/catalog/assets/{asset_id}",
    { params: { path: { asset_id: id } } },
  );
  if (!response.ok) {
    throw toApiError(error, response);
  }
}

export async function createPair(input: PairWrite): Promise<Pair> {
  const { data, error, response } = await api.POST("/api/v1/catalog/pairs", {
    body: input,
  });
  if (data === undefined) {
    throw toApiError(error, response);
  }
  return data;
}

export async function updatePair(id: number, input: PairWrite): Promise<Pair> {
  const { data, error, response } = await api.PATCH(
    "/api/v1/catalog/pairs/{pair_id}",
    { params: { path: { pair_id: id } }, body: input },
  );
  if (data === undefined) {
    throw toApiError(error, response);
  }
  return data;
}

export async function deletePair(id: number): Promise<void> {
  const { error, response } = await api.DELETE(
    "/api/v1/catalog/pairs/{pair_id}",
    { params: { path: { pair_id: id } } },
  );
  if (!response.ok) {
    throw toApiError(error, response);
  }
}

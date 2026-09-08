import type { Asset, AssetType, Pair } from "@/features/catalog/api";

export type SortDirection = "asc" | "desc";
export type AssetSortKey = "symbol" | "name" | "asset_type";
export type PairSortKey =
  "canonical_symbol" | "base" | "quote" | "type_relation";

const collator = new Intl.Collator(undefined, {
  numeric: true,
  sensitivity: "base",
});

function normalized(value: string): string {
  return value.trim().toLocaleLowerCase();
}

export function filterAssets(
  assets: Asset[],
  search: string,
  assetType: AssetType | "all",
): Asset[] {
  const term = normalized(search);
  return assets.filter((asset) => {
    const matchesType = assetType === "all" || asset.asset_type === assetType;
    const haystack = `${asset.symbol} ${asset.name ?? ""}`.toLocaleLowerCase();
    return matchesType && (!term || haystack.includes(term));
  });
}

export function filterPairs(pairs: Pair[], search: string): Pair[] {
  const term = normalized(search);
  if (!term) {
    return pairs;
  }
  return pairs.filter((pair) => {
    const haystack = [
      pair.canonical_symbol,
      pair.base.symbol,
      pair.base.name,
      pair.quote.symbol,
      pair.quote.name,
    ]
      .filter(Boolean)
      .join(" ")
      .toLocaleLowerCase();
    return haystack.includes(term);
  });
}

function compareText(
  left: string | null,
  right: string | null,
  direction: SortDirection,
): number {
  if (left === null) {
    return right === null ? 0 : 1;
  }
  if (right === null) {
    return -1;
  }
  const result = collator.compare(left, right);
  return direction === "asc" ? result : -result;
}

function assetSortValue(asset: Asset, key: AssetSortKey): string | null {
  if (key === "name") {
    return asset.name;
  }
  return asset[key];
}

function pairSortValue(pair: Pair, key: PairSortKey): string {
  if (key === "base") {
    return pair.base.symbol;
  }
  if (key === "quote") {
    return pair.quote.symbol;
  }
  if (key === "type_relation") {
    return `${pair.base.asset_type}/${pair.quote.asset_type}`;
  }
  return pair.canonical_symbol;
}

export function sortAssets(
  assets: Asset[],
  key: AssetSortKey,
  direction: SortDirection,
): Asset[] {
  return [...assets].sort((left, right) => {
    const result = compareText(
      assetSortValue(left, key),
      assetSortValue(right, key),
      direction,
    );
    return result || left.id - right.id;
  });
}

export function sortPairs(
  pairs: Pair[],
  key: PairSortKey,
  direction: SortDirection,
): Pair[] {
  return [...pairs].sort((left, right) => {
    const result = compareText(
      pairSortValue(left, key),
      pairSortValue(right, key),
      direction,
    );
    return result || left.id - right.id;
  });
}

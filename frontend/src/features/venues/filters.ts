/** Local search, visibility, and ordering for the venue workspace. */

import type {
  Instrument,
  Venue,
  VenueWalletAsset,
} from "@/features/venues/api";
import { compareText, type SortDirection } from "@/utils/sorting";

export type VisibilityFilter = "all" | "active" | "archived";
export type InstrumentSortKey =
  "exec_symbol" | "pair" | "product" | "settlement" | "status";
export type WalletAssetSortKey = "symbol" | "type" | "status";

function normalized(value: string): string {
  return value.trim().toLocaleLowerCase();
}

function matchesVisibility(
  isActive: boolean,
  visibility: VisibilityFilter,
): boolean {
  return (
    visibility === "all" ||
    (visibility === "active" && isActive) ||
    (visibility === "archived" && !isActive)
  );
}

export function filterVenues(
  venues: Venue[],
  search: string,
  visibility: VisibilityFilter,
): Venue[] {
  const term = normalized(search);
  return venues.filter((venue) => {
    const haystack = [venue.name, venue.description, venue.market_data_provider]
      .filter(Boolean)
      .join(" ")
      .toLocaleLowerCase();
    return (
      matchesVisibility(venue.is_active, visibility) &&
      (!term || haystack.includes(term))
    );
  });
}

export function filterInstruments(
  instruments: Instrument[],
  search: string,
  visibility: VisibilityFilter,
): Instrument[] {
  const term = normalized(search);
  return instruments.filter((instrument) => {
    const haystack = [
      instrument.exec_symbol,
      instrument.pair.canonical_symbol,
      instrument.product,
      instrument.settlement_asset?.symbol,
    ]
      .filter(Boolean)
      .join(" ")
      .toLocaleLowerCase();
    return (
      matchesVisibility(instrument.is_active, visibility) &&
      (!term || haystack.includes(term))
    );
  });
}

function instrumentValue(
  instrument: Instrument,
  key: InstrumentSortKey,
): string | null {
  if (key === "pair") {
    return instrument.pair.canonical_symbol;
  }
  if (key === "settlement") {
    return instrument.settlement_asset?.symbol ?? null;
  }
  if (key === "status") {
    return instrument.is_active ? "active" : "archived";
  }
  return instrument[key];
}

export function sortInstruments(
  instruments: Instrument[],
  key: InstrumentSortKey,
  direction: SortDirection,
): Instrument[] {
  return [...instruments].sort((left, right) => {
    const result = compareText(
      instrumentValue(left, key),
      instrumentValue(right, key),
      direction,
    );
    return result || left.id - right.id;
  });
}

export function filterWalletAssets(
  capabilities: VenueWalletAsset[],
  search: string,
  visibility: VisibilityFilter,
): VenueWalletAsset[] {
  const term = normalized(search);
  return capabilities.filter((capability) => {
    const haystack = [
      capability.asset.symbol,
      capability.asset.name,
      capability.asset.asset_type,
    ]
      .filter(Boolean)
      .join(" ")
      .toLocaleLowerCase();
    return (
      matchesVisibility(capability.is_active, visibility) &&
      (!term || haystack.includes(term))
    );
  });
}

function walletAssetValue(
  capability: VenueWalletAsset,
  key: WalletAssetSortKey,
): string {
  if (key === "type") {
    return capability.asset.asset_type;
  }
  if (key === "status") {
    return capability.is_active ? "active" : "archived";
  }
  return capability.asset.symbol;
}

export function sortWalletAssets(
  capabilities: VenueWalletAsset[],
  key: WalletAssetSortKey,
  direction: SortDirection,
): VenueWalletAsset[] {
  return [...capabilities].sort((left, right) => {
    const result = compareText(
      walletAssetValue(left, key),
      walletAssetValue(right, key),
      direction,
    );
    return result || left.id - right.id;
  });
}

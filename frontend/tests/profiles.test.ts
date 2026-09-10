import { beforeEach, describe, expect, it, vi } from "vitest";

import { reloadTokens } from "@/api/tokens";
import {
  createOperation,
  createProfile,
  deleteProfile,
  updateOperationNote,
  type Profile,
  type WalletOperation,
} from "@/features/profiles/api";
import { isPositiveDecimal } from "@/utils/decimal";

const profile: Profile = {
  id: 8,
  venue_type: "bybit",
  name: "Bybit Main",
  description: null,
  is_archived: false,
};
const operation: WalletOperation = {
  id: 12,
  wallet_asset_id: 9,
  kind: "deposit",
  amount: "1000.000000000000000000",
  note: null,
  created_at: "2026-09-08T10:00:00",
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

describe("profile setup flow", () => {
  it("validates positive exact decimals without floating-point conversion", () => {
    expect(isPositiveDecimal("0.000000000000000001")).toBe(true);
    expect(isPositiveDecimal("00.000")).toBe(false);
    expect(isPositiveDecimal("1e-8")).toBe(false);
  });

  it("creates a profile, records a ledger fact, and edits only its note", async () => {
    const requests: Request[] = [];
    const responses = [
      jsonResponse(profile, 201),
      jsonResponse(operation, 201),
      jsonResponse({ ...operation, note: "Initial capital" }),
      new Response(null, { status: 204 }),
    ];
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL) => {
        requests.push(input as Request);
        return responses.shift() as Response;
      }),
    );

    await createProfile({
      venue_type: profile.venue_type,
      name: profile.name,
      description: null,
    });
    await createOperation(profile.id, {
      wallet_asset_id: operation.wallet_asset_id,
      kind: "deposit",
      amount: "1000.000000000000000000",
      note: null,
    });
    await updateOperationNote(profile.id, operation.id, "Initial capital");
    await deleteProfile(profile.id);

    expect(requests.map((request) => request.method)).toEqual([
      "POST",
      "POST",
      "PATCH",
      "DELETE",
    ]);
    expect(await requests[2]?.clone().json()).toEqual({
      note: "Initial capital",
    });
    expect(new URL(requests[1]?.url ?? "").pathname).toBe(
      `/api/v1/profiles/${profile.id}/wallet/operations`,
    );
  });
});

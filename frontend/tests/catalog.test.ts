import { beforeEach, describe, expect, it, vi } from "vitest";
import { createApp, nextTick } from "vue";

import { reloadTokens } from "@/api/tokens";
import ConfirmDialog from "@/components/ConfirmDialog.vue";
import {
  createAsset,
  createPair,
  deletePair,
  type Asset,
  type Pair,
} from "@/features/catalog/api";

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
const reversePair: Pair = {
  id: 4,
  base: dollar,
  quote: bitcoin,
  canonical_symbol: "USD/BTC",
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

describe("catalog flow", () => {
  it("runs confirmation without closing the controlled dialog first", async () => {
    document.body.innerHTML =
      '<div class="tf-app"></div><div id="test-root"></div>';
    const onConfirm = vi.fn();
    const app = createApp(ConfirmDialog, {
      open: true,
      title: "Delete asset?",
      description: "This action cannot be undone.",
      confirmLabel: "Delete",
      cancelLabel: "Cancel",
      onConfirm,
    });

    app.mount("#test-root");
    await nextTick();
    const confirm = document.querySelector<HTMLButtonElement>(
      ".tf-confirm-dialog .button--danger",
    );
    confirm?.click();

    expect(confirm).not.toBeNull();
    expect(onConfirm).toHaveBeenCalledOnce();
    expect(document.querySelector(".tf-confirm-dialog")).not.toBeNull();
    app.unmount();
  });

  it("creates catalog dependencies in order and deletes an unused pair", async () => {
    const responses = [
      jsonResponse(bitcoin, 201),
      jsonResponse(dollar, 201),
      jsonResponse(pair, 201),
      new Response(null, { status: 204 }),
    ];
    const requests: Request[] = [];
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      requests.push(input as Request);
      return responses.shift() as Response;
    });
    vi.stubGlobal("fetch", fetchMock);

    await createAsset({ symbol: "BTC", name: "Bitcoin", asset_type: "crypto" });
    await createAsset({ symbol: "USD", name: "US Dollar", asset_type: "fiat" });
    const created = await createPair({ base_id: 1, quote_id: 2 });
    await deletePair(created.id);

    expect(created.canonical_symbol).toBe("BTC/USD");
    expect(fetchMock).toHaveBeenCalledTimes(4);
    expect(requests[2]?.method).toBe("POST");
    expect(requests[3]?.method).toBe("DELETE");
  });
});

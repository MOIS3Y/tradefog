import { beforeEach, describe, expect, it, vi } from "vitest";
import { createApp, nextTick } from "vue";

import { reloadTokens } from "@/api/tokens";
import ConfirmDialog from "@/components/ConfirmDialog.vue";
import {
  createAsset,
  createInstrument,
  deleteInstrument,
} from "@/features/profiles/marketApi";
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

  it("creates manual profile dependencies and deletes an unused instrument", async () => {
    const responses = [
      jsonResponse({ id: 1, symbol: "BTC" }, 201),
      jsonResponse({ id: 2, symbol: "USD" }, 201),
      jsonResponse({ id: 3, exec_symbol: "BTCUSD" }, 201),
      new Response(null, { status: 204 }),
    ];
    const requests: Request[] = [];
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      requests.push(input as Request);
      return responses.shift() as Response;
    });
    vi.stubGlobal("fetch", fetchMock);

    await createAsset(8, {
      symbol: "BTC",
      name: "Bitcoin",
      asset_type: "crypto",
    });
    await createAsset(8, {
      symbol: "USD",
      name: "US Dollar",
      asset_type: "fiat",
    });
    const created = await createInstrument(8, {
      mode: "manual",
      product: "spot",
      base: { symbol: "BTC" },
      quote: { symbol: "USD" },
      price_step: "0.01",
      qty_step: "0.001",
    });
    await deleteInstrument(8, created.id);

    expect(created.exec_symbol).toBe("BTCUSD");
    expect(new URL(requests[2]!.url).pathname).toBe(
      "/api/v1/profiles/8/instruments",
    );
    expect(fetchMock).toHaveBeenCalledTimes(4);
    expect(requests[2]?.method).toBe("POST");
    expect(requests[3]?.method).toBe("DELETE");
  });
});

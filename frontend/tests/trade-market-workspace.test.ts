/** Unsupported or failed market sources never remove position controls. */
import { afterEach, expect, it, vi } from "vitest";
import { createApp, h, nextTick, type App } from "vue";
import { createPinia } from "pinia";
import { QueryClient, VueQueryPlugin } from "@tanstack/vue-query";
import TradeMarketWorkspace from "@/features/trades/TradeMarketWorkspace.vue";
import type { Instrument } from "@/features/profiles/marketApi";

const instrument = {
  id: 1,
  profile_id: 2,
  exec_symbol: "BTCUSDT",
  product: "spot",
  price_step: "0.01",
  qty_step: "0.000001",
  base_asset_id: 1,
  quote_asset_id: 2,
  settlement_asset_id: 2,
  min_qty: null,
  min_notional: null,
  metadata_updated_at: null,
  is_active: true,
  is_archived: false,
} as Instrument;
let app: App | undefined;
let root: HTMLElement | undefined;
afterEach(() => {
  app?.unmount();
  root?.remove();
});

it.each(["manual", undefined] as const)(
  "keeps the ordinary position form for %s",
  async (provider) => {
    root = document.createElement("div");
    document.body.append(root);
    let edits = 0;
    app = createApp({
      render: () =>
        h(
          TradeMarketWorkspace,
          { instrument, tradeId: 1, venueType: provider },
          {
            default: () =>
              h(
                "button",
                {
                  onClick: () => {
                    edits++;
                  },
                },
                "Save position",
              ),
          },
        ),
    });
    app.use(createPinia());
    app.use(VueQueryPlugin, {
      queryClient: new QueryClient({
        defaultOptions: { queries: { retry: false } },
      }),
    });
    app.mount(root);
    await new Promise((resolve) => setTimeout(resolve, 20));
    await nextTick();
    expect(root.querySelector(".market-panel")).toBeNull();
    expect(root.querySelector(".trade-market-workspace--enabled")).toBeNull();
    root.querySelector("button")!.click();
    expect(edits).toBe(1);
  },
);

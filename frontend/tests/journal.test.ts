import { afterEach, describe, expect, it, vi } from "vitest";
import { createApp, nextTick, type App } from "vue";
import { createMemoryHistory, createRouter } from "vue-router";
import { QueryClient, VueQueryPlugin } from "@tanstack/vue-query";
import { i18n } from "@/i18n";
import TradeWorkspace from "@/features/trades/TradeWorkspace.vue";
import TradeRatingDisplay from "@/features/trades/TradeRatingDisplay.vue";
import RemoteCatalogSelect from "@/components/RemoteCatalogSelect.vue";

let app: App | undefined;
let queryClient: QueryClient | undefined;
afterEach(() => {
  app?.unmount();
  queryClient?.clear();
  vi.unstubAllGlobals();
  document.body.innerHTML = "";
});

function host(): void {
  document.body.innerHTML =
    '<div class="tf-app"><div id="test-root"></div></div>';
  i18n.global.locale.value = "en";
}

describe("paginated journal", () => {
  it("shows half stars and distinguishes an absent rating", async () => {
    host();
    app = createApp(TradeRatingDisplay, { value: 3 });
    app.use(i18n).mount("#test-root");
    expect(document.querySelectorAll(".journal-star")).toHaveLength(5);
    expect(
      document
        .querySelectorAll(".journal-star > span")[1]
        ?.getAttribute("style"),
    ).toContain("50%");
    expect(
      document.querySelector('[role="img"]')?.getAttribute("aria-label"),
    ).toContain("3");
    app.unmount();
    app = createApp(TradeRatingDisplay, { value: null });
    app.use(i18n).mount("#test-root");
    expect(
      [...document.querySelectorAll(".journal-star > span")].every((x) =>
        x.getAttribute("style")?.includes("0%"),
      ),
    ).toBe(true);
    expect(
      document.querySelector('[role="img"]')?.getAttribute("aria-label"),
    ).toBe(i18n.global.t("trades.rating.empty"));
  });

  it("sends sort and page to the server and keeps the return URL", async () => {
    host();
    const requests: URL[] = [];
    vi.stubGlobal(
      "fetch",
      vi.fn(async (request: Request) => {
        const url = new URL(request.url);
        requests.push(url);
        const body =
          url.pathname === "/api/v1/profiles"
            ? { items: [], total: 0, page: 1, page_size: 100 }
            : {
                items: [
                  {
                    id: 7,
                    profile_name: "Main",
                    strategy_name: "Breakout",
                    pair_symbol: "BTC/USDT",
                    exec_symbol: "BTCUSDT",
                    trade_date: "2026-09-09",
                    direction: "long",
                    status: "closed",
                    realized_pnl: "12.5",
                    settlement_symbol: "USDT",
                    quality_rating: 7,
                    review_completed_at: null,
                  },
                ],
                total: 80,
                page: Number(url.searchParams.get("page") ?? 1),
                page_size: 25,
              };
        return new Response(JSON.stringify(body), {
          headers: { "Content-Type": "application/json" },
        });
      }),
    );
    const router = createRouter({
      history: createMemoryHistory(),
      routes: [
        { path: "/trades", component: TradeWorkspace },
        { path: "/trades/:id", component: { template: "<div />" } },
      ],
    });
    await router.push(
      "/trades?page=2&sort=quality_rating&order=asc&review=unreviewed",
    );
    await router.isReady();
    queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });
    app = createApp(TradeWorkspace);
    app
      .use(router)
      .use(i18n)
      .use(VueQueryPlugin, { queryClient })
      .mount("#test-root");
    await vi.waitFor(() =>
      expect(document.querySelector(".journal-table")).not.toBeNull(),
    );
    const request = requests.find((x) => x.pathname === "/api/v1/trades")!;
    expect(request.searchParams.get("page")).toBe("2");
    expect(request.searchParams.get("review")).toBe("unreviewed");
    const more = document.querySelector<HTMLButtonElement>(
      '[aria-controls="trade-extra-filters"]',
    )!;
    expect(more.getAttribute("aria-expanded")).toBe("true");
    expect(more.textContent).toContain("(1)");
    more.click();
    await nextTick();
    expect(
      document.querySelector<HTMLElement>("#trade-extra-filters")?.style
        .display,
    ).toBe("none");
    expect(router.currentRoute.value.query.review).toBe("unreviewed");
    expect(
      document
        .querySelector('button[title="Reset"]')
        ?.closest("#trade-extra-filters"),
    ).toBeNull();
    const ratingHeader = [
      ...document.querySelectorAll<HTMLButtonElement>("th button"),
    ].find((x) =>
      x.textContent?.includes(i18n.global.t("trades.rating.label")),
    )!;
    ratingHeader.click();
    await vi.waitFor(() =>
      expect(router.currentRoute.value.query.order).toBe("desc"),
    );
    expect(router.currentRoute.value.query.page).toBeUndefined();
    await vi.waitFor(() =>
      expect(
        document.querySelector(".journal-table a")?.getAttribute("href"),
      ).toContain("returnTo="),
    );
    await nextTick();
    const link = document.querySelector<HTMLAnchorElement>(".journal-table a")!;
    const target = new URL(link.href);
    expect(target.pathname).toBe("/trades/7");
    expect(target.searchParams.get("returnTo")).toBe(
      router.currentRoute.value.fullPath,
    );
    const reset = document.querySelector<HTMLButtonElement>(
      `button[title="${i18n.global.t("catalog.reset")}"]`,
    )!;
    reset.click();
    await vi.waitFor(() => expect(router.currentRoute.value.query).toEqual({}));
    expect(more.textContent).not.toContain("(1)");
    expect(document.querySelector(".journal-table tbody td")?.textContent).toBe(
      "#7",
    );
    await vi.waitFor(() =>
      expect(
        requests.some(
          (url) =>
            url.pathname === "/api/v1/trades" &&
            url.searchParams.get("sort") === "id" &&
            url.searchParams.get("order") === "desc",
        ),
      ).toBe(true),
    );
    const idHeader = document.querySelector(".journal-table th")!;
    expect(idHeader.getAttribute("aria-sort")).toBe("descending");
    idHeader.querySelector("button")!.click();
    await vi.waitFor(() =>
      expect(router.currentRoute.value.query).toMatchObject({
        sort: "id",
        order: "asc",
      }),
    );
  });

  it("resolves a selected asset outside the first option page", async () => {
    host();
    const paths: string[] = [];
    vi.stubGlobal(
      "fetch",
      vi.fn(async (request: Request) => {
        paths.push(new URL(request.url).pathname);
        return new Response(
          JSON.stringify({
            id: 999,
            symbol: "LATE",
            name: "Later page",
            asset_type: "crypto",
          }),
          { headers: { "Content-Type": "application/json" } },
        );
      }),
    );
    queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });
    app = createApp(RemoteCatalogSelect, {
      modelValue: 999,
      profileId: 8,
      resource: "assets",
      placeholder: "Asset",
      emptyLabel: "No assets",
    });
    app.use(i18n).use(VueQueryPlugin, { queryClient }).mount("#test-root");
    await vi.waitFor(() =>
      expect(document.querySelector("input")?.value).toBe("LATE"),
    );
    expect(paths).toEqual(["/api/v1/profiles/8/assets/999"]);
  });
});

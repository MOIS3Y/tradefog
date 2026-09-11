/** Empty denominations remain discoverable without manufacturing funds. */
import { afterEach, expect, it, vi } from "vitest";
import { createApp, type App } from "vue";
import { createPinia } from "pinia";
import { QueryClient, VueQueryPlugin } from "@tanstack/vue-query";
import { i18n } from "@/i18n";
import ProfileWallet from "@/features/profiles/ProfileWallet.vue";
import { reloadTokens } from "@/api/tokens";

let app: App;
let query: QueryClient;
afterEach(() => {
  app?.unmount();
  query?.clear();
  vi.unstubAllGlobals();
  document.body.innerHTML = "";
});

it.each(["manual", "bybit"] as const)(
  "keeps %s balances separate from profile operations",
  async (venue) => {
    document.body.innerHTML = '<div class="tf-app"><div id="root"></div></div>';
    localStorage.clear();
    reloadTokens();
    i18n.global.locale.value = "en";
    const requests: Request[] = [];
    const asset = {
      id: 9,
      profile_id: 8,
      symbol: "BTC",
      name: "Bitcoin",
      asset_type: "crypto",
      is_archived: false,
      risk_stop_capital: null,
      status: "active",
      balance: "0",
      reserved: "0",
      allocated: "0",
      available: "0",
      uncommitted: "0",
    };
    vi.stubGlobal(
      "fetch",
      vi.fn(async (request: Request) => {
        requests.push(request);
        const url = new URL(request.url);
        const items =
          url.pathname.endsWith("/operations") ||
          url.searchParams.get("hide_empty") === "true"
            ? []
            : [asset];
        return new Response(
          JSON.stringify({
            items,
            total: items.length,
            page: 1,
            page_size: 25,
          }),
          {
            headers: { "Content-Type": "application/json" },
          },
        );
      }),
    );
    query = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    app = createApp(ProfileWallet, {
      profile: {
        id: 8,
        venue_type: venue,
        name: "Manual",
        description: null,
        is_archived: false,
      },
    });
    app
      .use(createPinia())
      .use(i18n)
      .use(VueQueryPlugin, { queryClient: query })
      .mount("#root");
    await vi.waitFor(() =>
      expect(requests.some((r) => r.url.includes("hide_empty=true"))).toBe(
        true,
      ),
    );
    expect(document.body.textContent).not.toContain("Bitcoin");
    const toggle =
      document.querySelector<HTMLButtonElement>('[role="switch"]')!;
    expect(toggle.getAttribute("aria-checked")).toBe("true");
    expect(document.body.textContent?.includes("Add asset")).toBe(
      venue === "manual",
    );
    toggle.click();
    await vi.waitFor(() =>
      expect(
        requests.some((r) => r.url.includes("/profiles/8/operations")),
      ).toBe(true),
    );
    await vi.waitFor(() =>
      expect(document.body.textContent).toContain("Bitcoin"),
    );
    expect(
      document.querySelector(".wallet-balance-card__name")?.textContent,
    ).toBe("Bitcoin · Crypto");
    document
      .querySelector<HTMLButtonElement>('[aria-label="Asset types"]')!
      .dispatchEvent(
        new KeyboardEvent("keydown", { key: "ArrowDown", bubbles: true }),
      );
    await vi.waitFor(() =>
      expect(document.querySelector('[role="option"]')).not.toBeNull(),
    );
    const labels = [...document.querySelectorAll('[role="option"]')].map(
      (item) => item.textContent?.trim(),
    );
    expect(labels.includes("Equity")).toBe(venue === "manual");
    expect(toggle.getAttribute("aria-checked")).toBe("false");
    expect(requests.every((r) => r.method === "GET")).toBe(true);
    expect(
      new URL(
        requests.find((r) => r.url.includes("/operations"))!.url,
      ).searchParams.get("asset_id"),
    ).toBe("9");
    expect(document.querySelector(".wallet-summary")).toBeNull();
    expect(document.querySelector("button button")).toBeNull();
    expect(requests.some((r) => r.url.includes("hide_empty=false"))).toBe(true);
  },
);

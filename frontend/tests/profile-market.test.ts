/** Setup UI keeps manual independent and imports only the chosen symbol. */
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { createApp, type App } from "vue";
import { createPinia } from "pinia";
import { QueryClient, VueQueryPlugin } from "@tanstack/vue-query";
import { i18n } from "@/i18n";
import { reloadTokens } from "@/api/tokens";
import ProfileMarket from "@/features/profiles/ProfileMarket.vue";
import type { VenueType } from "@/features/profiles/marketApi";

let app: App;
let query: QueryClient;
const requests: Request[] = [];
beforeEach(() => {
  document.body.innerHTML = '<div class="tf-app"><div id="root"></div></div>';
  localStorage.clear();
  reloadTokens();
  i18n.global.locale.value = "en";
  requests.length = 0;
  vi.stubGlobal(
    "fetch",
    vi.fn(async (request: Request) => {
      requests.push(request);
      const path = new URL(request.url).pathname;
      const body = path.includes("/public/")
        ? {
            items: [
              {
                symbol: "BTCUSDT",
                product: "spot",
                base: "BTC",
                quote: "USDT",
                settlement: "USDT",
                price_step: "0.01",
                qty_step: "0.001",
                min_qty: null,
                min_notional: null,
                is_active: true,
              },
            ],
            next_cursor: null,
          }
        : request.method === "POST"
          ? { id: 1, exec_symbol: "BTCUSDT" }
          : { items: [], total: 0, page: 1, page_size: 25 };
      return new Response(JSON.stringify(body), {
        status: request.method === "POST" ? 201 : 200,
        headers: { "Content-Type": "application/json" },
      });
    }),
  );
});
afterEach(() => {
  app?.unmount();
  query?.clear();
  vi.unstubAllGlobals();
  document.body.innerHTML = "";
});
function mount(venue: VenueType): void {
  query = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  app = createApp(ProfileMarket, {
    profile: {
      id: 8,
      venue_type: venue,
      name: "Main",
      description: null,
      is_archived: false,
    },
  });
  app
    .use(createPinia())
    .use(i18n)
    .use(VueQueryPlugin, { queryClient: query })
    .mount("#root");
}
function button(text: string): HTMLButtonElement {
  const found = [
    ...document.querySelectorAll<HTMLButtonElement>("button"),
  ].find((item) => item.textContent?.trim() === text);
  if (!found) throw new Error("Missing button: " + text);
  return found;
}
it("allows manual setup without exchange requests or staff catalogs", async () => {
  mount("manual");
  await vi.waitFor(() => expect(requests.length).toBe(1));
  button("Assets").click();
  await vi.waitFor(() =>
    expect(requests.some((r) => r.url.includes("/profiles/8/assets"))).toBe(
      true,
    ),
  );
  button("Add asset").click();
  await vi.waitFor(() =>
    expect(document.querySelector('[role="dialog"]')).not.toBeNull(),
  );
  expect(
    requests.every(
      (r) => !r.url.includes("/venues/") && !r.url.includes("/catalog/"),
    ),
  ).toBe(true);
  expect(document.querySelector('[role="dialog"]')?.textContent).toContain(
    "Asset type",
  );
});
it("browses on demand and imports metadata without funding a wallet", async () => {
  mount("bybit");
  await vi.waitFor(() => expect(requests.length).toBe(1));
  expect(requests[0]!.url).not.toContain("/public/");
  button("Import instrument").click();
  await vi.waitFor(() =>
    expect(document.querySelector('input[type="radio"]')).not.toBeNull(),
  );
  const radio = document.querySelector<HTMLInputElement>(
    'input[type="radio"]',
  )!;
  radio.checked = true;
  radio.dispatchEvent(new Event("change", { bubbles: true }));
  await vi.waitFor(() =>
    expect(
      document.querySelector<HTMLButtonElement>(
        '[role="dialog"] button[type="submit"]',
      )?.disabled,
    ).toBe(false),
  );
  document
    .querySelector<HTMLButtonElement>('[role="dialog"] button[type="submit"]')!
    .click();
  await vi.waitFor(() =>
    expect(requests.some((r) => r.method === "POST")).toBe(true),
  );
  const imported = requests.find((r) => r.method === "POST")!;
  expect(new URL(imported.url).pathname).toBe("/api/v1/profiles/8/instruments");
  expect(await imported.clone().json()).toEqual({
    exec_symbol: "BTCUSDT",
    product: "spot",
    name: null,
  });
  expect(requests.every((r) => !r.url.includes("/wallet"))).toBe(true);
});

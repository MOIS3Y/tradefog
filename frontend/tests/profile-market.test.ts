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
  HTMLElement.prototype.scrollIntoView = vi.fn();
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
  button("Add instrument").click();
  await vi.waitFor(() =>
    expect(requests.some((r) => r.url.includes("/profiles/8/assets"))).toBe(
      true,
    ),
  );
  await vi.waitFor(() =>
    expect(document.querySelector('[role="dialog"]')).not.toBeNull(),
  );
  expect(
    requests.every(
      (r) => !r.url.includes("/venues/") && !r.url.includes("/catalog/"),
    ),
  ).toBe(true);
  expect(document.querySelector('[role="dialog"]')?.textContent).toContain(
    "Base asset",
  );
});
it("opens instrument decimals without storage padding and preserves exact edits", async () => {
  const instrument = {
    id: 11,
    profile_id: 8,
    exec_symbol: "ABC/RUB",
    product: "cash_equity",
    base_asset_id: 1,
    quote_asset_id: 2,
    settlement_asset_id: 2,
    base_asset_type: "equity",
    quote_asset_type: "fiat",
    price_step: "0.010000000000000000",
    qty_step: "1.000000000000000000",
    min_qty: "0.000000010000000000",
    min_notional: "250.125000000000000000",
    is_active: true,
    is_archived: false,
  };
  vi.stubGlobal(
    "fetch",
    vi.fn(async (request: Request) => {
      requests.push(request);
      const path = new URL(request.url).pathname;
      const body = path.endsWith("/assets/1")
        ? { id: 1, symbol: "ABC", asset_type: "equity" }
        : path.endsWith("/assets/2")
          ? { id: 2, symbol: "RUB", asset_type: "fiat" }
          : request.method === "PATCH"
            ? instrument
            : { items: [instrument], total: 1, page: 1, page_size: 25 };
      return new Response(JSON.stringify(body), {
        headers: { "Content-Type": "application/json" },
      });
    }),
  );
  mount("manual");
  await vi.waitFor(() =>
    expect(document.querySelector('button[aria-label="Edit"]')).not.toBeNull(),
  );
  document
    .querySelector<HTMLButtonElement>('button[aria-label="Edit"]')!
    .click();
  await vi.waitFor(() =>
    expect(document.querySelector('[role="dialog"]')).not.toBeNull(),
  );
  const inputs = [
    ...document.querySelectorAll<HTMLInputElement>(
      '[role="dialog"] input[inputmode="decimal"]',
    ),
  ];
  expect(inputs.map((input) => input.value)).toEqual([
    "0.01",
    "1",
    "0.00000001",
    "250.125",
  ]);
  inputs[2]!.value = "0.000000012345678901";
  inputs[2]!.dispatchEvent(new Event("input", { bubbles: true }));
  document
    .querySelector('[role="dialog"] form')!
    .dispatchEvent(new Event("submit", { bubbles: true, cancelable: true }));
  await vi.waitFor(() =>
    expect(requests.some((request) => request.method === "PATCH")).toBe(true),
  );
  const body = await requests
    .find((request) => request.method === "PATCH")!
    .clone()
    .json();
  expect(body).toMatchObject({
    price_step: "0.01",
    qty_step: "1",
    min_qty: "0.000000012345678901",
    min_notional: "250.125",
  });
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
    mode: "bybit",
  });
  expect(requests.every((r) => !r.url.includes("/wallet"))).toBe(true);
});

it("creates manual pair assets inline in one instrument request", async () => {
  mount("manual");
  await vi.waitFor(() => expect(requests.length).toBe(1));
  button("Add instrument").click();
  await vi.waitFor(() =>
    expect(document.querySelectorAll(".asset-symbol-field input").length).toBe(
      2,
    ),
  );
  for (const [index, symbol] of ["BTC", "USDT"].entries()) {
    const input = document.querySelectorAll<HTMLInputElement>(
      ".asset-symbol-field input",
    )[index]!;
    const trigger = document.querySelectorAll<HTMLButtonElement>(
      ".asset-symbol-field .tf-combobox-trigger",
    )[index]!;
    trigger.click();
    await vi.waitFor(() =>
      expect(input.getAttribute("aria-expanded")).toBe("true"),
    );
    input.value = symbol;
    input.dispatchEvent(new Event("input", { bubbles: true }));
    await vi.waitFor(() => {
      const option = [
        ...document.querySelectorAll<HTMLElement>('[role="option"]'),
      ].find((item) => item.textContent?.includes("Create " + symbol));
      expect(option).toBeDefined();
    });
    const option = [
      ...document.querySelectorAll<HTMLElement>('[role="option"]'),
    ].find((item) => item.textContent?.includes("Create " + symbol))!;
    option.click();
  }
  const submit = document.querySelector<HTMLButtonElement>(
    '[role="dialog"] button[type="submit"]',
  )!;
  await vi.waitFor(() => expect(submit.disabled).toBe(false));
  submit.click();
  await vi.waitFor(() =>
    expect(requests.some((r) => r.method === "POST")).toBe(true),
  );
  expect(
    await requests
      .find((r) => r.method === "POST")!
      .clone()
      .json(),
  ).toMatchObject({
    mode: "manual",
    base: { symbol: "BTC", asset_type: "crypto" },
    quote: { symbol: "USDT", asset_type: "crypto" },
  });
  expect(requests.filter((r) => r.method === "POST")).toHaveLength(1);
});

it("renders ordered asset types without fetching each asset", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (request: Request) => {
      requests.push(request);
      return new Response(
        JSON.stringify({
          items: [
            {
              id: 1,
              profile_id: 8,
              exec_symbol: "BTC/USD",
              product: "spot",
              base_asset_id: 1,
              quote_asset_id: 2,
              settlement_asset_id: 2,
              base_asset_type: "crypto",
              quote_asset_type: "fiat",
              price_step: "0.01",
              qty_step: "0.001",
              is_active: true,
              is_archived: false,
            },
          ],
          total: 1,
          page: 1,
          page_size: 25,
        }),
        { headers: { "Content-Type": "application/json" } },
      );
    }),
  );
  mount("manual");
  await vi.waitFor(() =>
    expect(document.querySelector(".asset-type-pair")?.textContent).toMatch(
      /Crypto\s*\/\s*Fiat/,
    ),
  );
  expect(requests).toHaveLength(1);
});

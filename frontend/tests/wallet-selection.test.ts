/** Selection, explicit funding and operation targets cannot cross assets. */
import { afterEach, expect, it, vi } from "vitest";
import { createApp, type App } from "vue";
import { createPinia } from "pinia";
import { QueryClient, VueQueryPlugin } from "@tanstack/vue-query";
import ProfileWallet from "@/features/profiles/ProfileWallet.vue";
import { i18n } from "@/i18n";
import { reloadTokens } from "@/api/tokens";

let app: App;
let query: QueryClient;
afterEach(() => {
  app?.unmount();
  query?.clear();
  vi.unstubAllGlobals();
  document.body.innerHTML = "";
});

async function mount(focusAssetId?: number) {
  document.body.innerHTML = '<div class="tf-app"><div id="root"></div></div>';
  localStorage.clear();
  reloadTokens();
  i18n.global.locale.value = "en";
  const requests: Request[] = [];
  const asset = (id: number) => ({
    id,
    profile_id: 8,
    symbol: id === 1 ? "BTC" : "USDT",
    name: null,
    asset_type: id === 1 ? "crypto" : "fiat",
    is_archived: false,
    risk_stop_capital: "0",
    status: "active",
    balance: "10",
    allocated: "0",
    reserved: "0",
    available: "10",
    uncommitted: "10",
  });
  vi.stubGlobal(
    "fetch",
    vi.fn(async (request: Request) => {
      requests.push(request);
      const url = new URL(request.url);
      let data: unknown;
      if (url.pathname.endsWith("/assets/2")) data = asset(2);
      else if (url.pathname.endsWith("/operations")) {
        const id = Number(url.searchParams.get("asset_id"));
        const items = [
          {
            id,
            asset_id: id,
            asset_symbol: asset(id).symbol,
            kind: "deposit",
            amount: String(id),
            note: `Ledger ${id}`,
            created_at: "2026-09-10T12:00:00",
          },
        ];
        data = { items, total: 1, page: 1, page_size: 25 };
      } else {
        const items =
          url.searchParams.get("q") === "NONE"
            ? []
            : focusAssetId
              ? [asset(1)]
              : [asset(1), asset(2)];
        const filtered = items.filter(
          (item) =>
            !url.searchParams.has("asset_type") ||
            item.asset_type === url.searchParams.get("asset_type"),
        );
        data = {
          items: filtered,
          total: filtered.length,
          page: 1,
          page_size: 25,
        };
      }
      return new Response(JSON.stringify(data), {
        headers: { "Content-Type": "application/json" },
      });
    }),
  );
  query = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  app = createApp(ProfileWallet, {
    profile: {
      id: 8,
      venue_type: "manual",
      name: "Main",
      description: null,
      is_archived: false,
    },
    focusAssetId,
  });
  app
    .use(createPinia())
    .use(i18n)
    .use(VueQueryPlugin, { queryClient: query })
    .mount("#root");
  await vi.waitFor(() =>
    expect(document.querySelector(".profile-ledger")).not.toBeNull(),
  );
  return requests;
}

it("follows card selection and binds an open operation form to its asset", async () => {
  const requests = await mount();
  expect(
    document.querySelector(".wallet-balance-card__name")?.textContent,
  ).toBe("Crypto");
  const cards = document.querySelectorAll<HTMLButtonElement>(
    ".wallet-balance-card__select",
  );
  await vi.waitFor(() =>
    expect(document.body.textContent).toContain("Ledger 1"),
  );
  cards[1]!.click();
  await vi.waitFor(() =>
    expect(document.body.textContent).toContain("Ledger 2"),
  );
  expect(document.body.textContent).not.toContain("Ledger 1");
  expect(document.querySelector(".wallet-summary")).toBeNull();
  document
    .querySelector<HTMLButtonElement>('[aria-label="Record operation · BTC"]')!
    .click();
  await vi.waitFor(() =>
    expect(document.querySelector('[role="dialog"]')).not.toBeNull(),
  );
  // Even a programmatic selection change must not retarget the open form.
  cards[1]!.click();
  const input = document.querySelector<HTMLInputElement>(
    '[role="dialog"] input[inputmode="decimal"]',
  )!;
  input.value = "5";
  input.dispatchEvent(new Event("input", { bubbles: true }));
  document
    .querySelector<HTMLFormElement>('[role="dialog"] form')!
    .dispatchEvent(new Event("submit", { bubbles: true, cancelable: true }));
  await vi.waitFor(() =>
    expect(requests.some((r) => r.method === "POST")).toBe(true),
  );
  expect(new URL(requests.find((r) => r.method === "POST")!.url).pathname).toBe(
    "/api/v1/profiles/8/assets/1/operations",
  );
});

it("resolves an explicitly funded off-page asset, then clears selection for an empty search", async () => {
  const requests = await mount(2);
  await vi.waitFor(() =>
    expect(document.body.textContent).toContain("Ledger 2"),
  );
  expect(document.querySelectorAll(".wallet-balance-card")).toHaveLength(2);
  const input = document.querySelector<HTMLInputElement>(
    '[aria-label="Search assets"]',
  )!;
  input.value = "NONE";
  input.dispatchEvent(new Event("input", { bubbles: true }));
  await vi.waitFor(() =>
    expect(document.querySelector(".profile-ledger")).toBeNull(),
  );
  expect(
    requests
      .filter((r) => r.url.includes("/operations"))
      .every((r) => new URL(r.url).searchParams.has("asset_id")),
  ).toBe(true);
});

it("filters asset types and clears the ledger for an empty result", async () => {
  const requests = await mount();
  async function choose(text: string) {
    document
      .querySelector<HTMLButtonElement>('[aria-label="Asset types"]')!
      .dispatchEvent(
        new KeyboardEvent("keydown", { key: "ArrowDown", bubbles: true }),
      );
    await vi.waitFor(() =>
      expect(document.querySelector('[role="option"]')).not.toBeNull(),
    );
    const option = [
      ...document.querySelectorAll<HTMLElement>('[role="option"]'),
    ].find((item) => item.textContent?.trim() === text)!;
    option.dispatchEvent(
      new KeyboardEvent("keydown", { key: "Enter", bubbles: true }),
    );
  }
  await choose("Fiat");
  await vi.waitFor(() =>
    expect(document.body.textContent).toContain("Ledger 2"),
  );
  expect(document.querySelectorAll(".wallet-balance-card")).toHaveLength(1);
  const request = requests.find(
    (r) => new URL(r.url).searchParams.get("asset_type") === "fiat",
  )!;
  expect(new URL(request.url).searchParams.get("hide_empty")).toBe("true");
  expect(new URL(request.url).searchParams.get("page")).toBe("1");
  await choose("Equity");
  await vi.waitFor(() =>
    expect(document.querySelectorAll(".wallet-balance-card")).toHaveLength(0),
  );
  expect(document.body.textContent).not.toContain("Ledger 2");
});

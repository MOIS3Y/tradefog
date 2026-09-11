/** Ledger filters use server metadata independently of paged balance cards. */
import { afterEach, expect, it, vi } from "vitest";
import { createApp, h, reactive, type App } from "vue";
import { createPinia } from "pinia";
import { QueryClient, VueQueryPlugin } from "@tanstack/vue-query";
import ProfileOperations from "@/features/profiles/ProfileOperations.vue";
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

it("keeps filters but resets pagination and hides previous rows on asset change", async () => {
  document.body.innerHTML = '<div class="tf-app"><div id="root"></div></div>';
  localStorage.clear();
  reloadTokens();
  i18n.global.locale.value = "en";
  const props = reactive({
    profileId: 8,
    assetId: 1 as number | null,
    assetSymbol: "BTC",
  });
  const requests: URL[] = [];
  let release: (() => void) | undefined;
  vi.stubGlobal(
    "fetch",
    vi.fn(async (request: Request) => {
      const url = new URL(request.url);
      requests.push(url);
      const id = Number(url.searchParams.get("asset_id"));
      if (id === 2)
        await new Promise<void>((resolve) => {
          release = resolve;
        });
      return new Response(
        JSON.stringify({
          items: [
            {
              id,
              asset_id: id,
              asset_symbol: id === 1 ? "BTC" : "USDT",
              kind: "deposit",
              amount: "1",
              note: `Record ${id}`,
              created_at: "2026-09-10T12:00:00",
            },
          ],
          total: 30,
          page: Number(url.searchParams.get("page")),
          page_size: 25,
        }),
        { headers: { "Content-Type": "application/json" } },
      );
    }),
  );
  query = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  app = createApp({ render: () => h(ProfileOperations, props) });
  app
    .use(createPinia())
    .use(i18n)
    .use(VueQueryPlugin, { queryClient: query })
    .mount("#root");
  await vi.waitFor(() =>
    expect(document.body.textContent).toContain("Record 1"),
  );
  const from = document.querySelector<HTMLInputElement>('input[type="date"]')!;
  from.value = "2026-01-01";
  from.dispatchEvent(new Event("input", { bubbles: true }));
  await vi.waitFor(() =>
    expect(requests.at(-1)?.searchParams.get("date_from")).toBe("2026-01-01"),
  );
  await vi.waitFor(() =>
    expect(document.querySelectorAll(".pagination__arrow")).toHaveLength(2),
  );
  document
    .querySelectorAll<HTMLButtonElement>(".pagination__arrow")[1]!
    .click();
  await vi.waitFor(() =>
    expect(requests.at(-1)?.searchParams.get("page")).toBe("2"),
  );
  props.assetId = 2;
  props.assetSymbol = "USDT";
  await vi.waitFor(() => expect(release).toBeDefined());
  expect(document.body.textContent).not.toContain("Record 1");
  expect(requests.at(-1)?.searchParams.get("page")).toBe("1");
  expect(requests.at(-1)?.searchParams.get("date_from")).toBe("2026-01-01");
  release!();
  await vi.waitFor(() =>
    expect(document.body.textContent).toContain("Record 2"),
  );
  const count = requests.length;
  props.assetId = null;
  await vi.waitFor(() =>
    expect(document.querySelector(".profile-ledger")).toBeNull(),
  );
  expect(requests).toHaveLength(count);
});

it("sorts and filters the profile ledger, rejects inverted dates and resets", async () => {
  document.body.innerHTML = '<div class="tf-app"><div id="root"></div></div>';
  localStorage.clear();
  reloadTokens();
  i18n.global.locale.value = "en";
  const requests: URL[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (request: Request) => {
      const url = new URL(request.url);
      requests.push(url);
      const items = url.searchParams.has("date_from")
        ? []
        : [
            {
              id: 5,
              asset_id: 99,
              asset_symbol: "XRP",
              kind: "deposit",
              amount: "1E-8",
              note: null,
              created_at: "2026-09-10T12:00:00",
            },
          ];
      return new Response(
        JSON.stringify({ items, total: items.length, page: 1, page_size: 25 }),
        { headers: { "Content-Type": "application/json" } },
      );
    }),
  );
  query = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  app = createApp(ProfileOperations, {
    profileId: 8,
    assetId: 99,
    assetSymbol: "XRP",
  });
  app
    .use(createPinia())
    .use(i18n)
    .use(VueQueryPlugin, { queryClient: query })
    .mount("#root");
  await vi.waitFor(() => expect(document.body.textContent).toContain("XRP"));
  await vi.waitFor(() =>
    expect(document.body.textContent).toContain("+0.00000001"),
  );
  expect(requests.at(-1)?.searchParams.get("asset_id")).toBe("99");
  document.querySelector<HTMLButtonElement>("th button")!.click();
  await vi.waitFor(() =>
    expect(requests.at(-1)?.searchParams.get("order")).toBe("asc"),
  );
  expect(document.querySelector(".ledger-kind--deposit")).not.toBeNull();
  expect(document.querySelector(".ledger-row__amount--deposit")).not.toBeNull();
  document.querySelectorAll<HTMLButtonElement>("th button")[1]!.click();
  await vi.waitFor(() =>
    expect(requests.at(-1)?.searchParams.get("sort")).toBe("kind"),
  );
  expect(requests.at(-1)?.searchParams.get("order")).toBe("asc");
  document.querySelectorAll<HTMLButtonElement>("th button")[1]!.click();
  await vi.waitFor(() =>
    expect(requests.at(-1)?.searchParams.get("order")).toBe("desc"),
  );
  const dates =
    document.querySelectorAll<HTMLInputElement>('input[type="date"]');
  dates[0]!.value = "2026-10-01";
  dates[0]!.dispatchEvent(new Event("input", { bubbles: true }));
  await vi.waitFor(() =>
    expect(document.body.textContent).toContain("No operations match"),
  );
  const count = requests.length;
  dates[1]!.value = "2026-09-01";
  dates[1]!.dispatchEvent(new Event("input", { bubbles: true }));
  await vi.waitFor(() =>
    expect(document.querySelector(".field-error")).not.toBeNull(),
  );
  expect(requests).toHaveLength(count);
  document.querySelector<HTMLButtonElement>(".ledger-reset")!.click();
  await vi.waitFor(() => expect(document.body.textContent).toContain("XRP"));
  expect(document.querySelector(".field-error")).toBeNull();
});

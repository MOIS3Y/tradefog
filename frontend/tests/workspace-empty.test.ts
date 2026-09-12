/** First-run guidance must not masquerade as a filtered empty collection. */
import { afterEach, expect, it, vi } from "vitest";
import { createApp, type App } from "vue";
import { createPinia } from "pinia";
import { createRouter, createMemoryHistory } from "vue-router";
import { QueryClient, VueQueryPlugin } from "@tanstack/vue-query";
import TradeWorkspace from "@/features/trades/TradeWorkspace.vue";
import ProfileWorkspace from "@/features/profiles/ProfileWorkspace.vue";
import { hasTradeFilters } from "@/features/trades/filters";
import type { TradeListParams } from "@/features/trades/api";
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

async function mount(
  path: string,
  active = 0,
  archived = 0,
  failedPresence = false,
) {
  document.body.innerHTML = '<div class="tf-app"><div id="root"></div></div>';
  localStorage.clear();
  reloadTokens();
  i18n.global.locale.value = "ru";
  const requests: URL[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (request: Request) => {
      const url = new URL(request.url);
      requests.push(url);
      if (failedPresence && url.searchParams.get("visibility") === "all") {
        return new Response("{}", { status: 503 });
      }
      let total = 0;
      let items: unknown[] = [];
      if (url.pathname === "/api/v1/profiles") {
        total = url.searchParams.get("q")
          ? 0
          : url.searchParams.get("visibility") === "all"
            ? active + archived
            : active;
        if (total)
          items = [
            {
              id: 1,
              name: "Main",
              venue_type: "manual",
              description: null,
              is_archived: !active,
            },
          ];
      }
      const body =
        url.pathname === "/api/v1/venues"
          ? []
          : { items, total, page: 1, page_size: 25 };
      return new Response(JSON.stringify(body), {
        headers: { "Content-Type": "application/json" },
      });
    }),
  );
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: "/trades", component: TradeWorkspace },
      { path: "/profiles", component: ProfileWorkspace },
      { path: "/trades/new", component: { template: "<p>New trade</p>" } },
    ],
  });
  await router.push(path);
  await router.isReady();
  query = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  app = createApp({ template: "<RouterView />" });
  app
    .use(createPinia())
    .use(i18n)
    .use(router)
    .use(VueQueryPlugin, { queryClient: query })
    .mount("#root");
  return { router, requests };
}

function state() {
  return document.querySelector(".state-panel--empty");
}

it.each([
  [0, 0, "Начните с торгового профиля", "/profiles"],
  [1, 0, "У вас пока нет сделок", "/profiles"],
  [0, 1, "Нет активных торговых профилей", "/profiles"],
] as const)(
  "guides an empty journal with %i active and %i archived profiles",
  async (active, archived, title, target) => {
    const { router } = await mount(
      "/trades?sort=quality_rating&order=asc&page_size=50",
      active,
      archived,
    );
    await vi.waitFor(() => expect(state()?.textContent).toContain(title));
    expect(state()?.querySelector("p")?.textContent?.length).toBeGreaterThan(
      20,
    );
    state()?.querySelector<HTMLElement>("a, button")?.click();
    await vi.waitFor(() => expect(router.currentRoute.value.path).toBe(target));
  },
);

it.each([
  "q=BTC",
  "trade_status=closed",
  "period=week",
  "profile_id=1",
  "strategy_id=1",
  "direction=short",
  "review=reviewed",
  "rating=unrated",
  "period=custom&date_from=2026-01-01",
])(
  "keeps the filtered message for %s and resets restrictions",
  async (filter) => {
    const { router, requests } = await mount("/trades?" + filter, 1);
    await vi.waitFor(() =>
      expect(state()?.textContent).toContain(
        i18n.global.t("trades.emptyFiltered"),
      ),
    );
    expect(state()?.querySelector("p")?.textContent).toBe(
      "Измените условия поиска или сбросьте фильтры.",
    );
    expect(
      requests.some(
        (url) =>
          url.pathname === "/api/v1/profiles" &&
          url.searchParams.get("visibility") === "all",
      ),
    ).toBe(false);
    state()?.querySelector<HTMLButtonElement>("button")?.click();
    await vi.waitFor(() => expect(router.currentRoute.value.query).toEqual({}));
    await vi.waitFor(() =>
      expect(state()?.textContent).toContain("У вас пока нет сделок"),
    );
  },
);

it("offers profile creation with the default active visibility", async () => {
  await mount("/profiles");
  await vi.waitFor(() =>
    expect(state()?.textContent).toContain("У вас пока нет торговых профилей"),
  );
  expect(document.querySelector(".profile-console")).toBeNull();
  state()?.querySelector<HTMLButtonElement>("button")?.click();
  await vi.waitFor(() =>
    expect(document.querySelector('[role="dialog"]')).not.toBeNull(),
  );
});

it("shows archived profiles after resetting an empty active selection", async () => {
  await mount("/profiles", 0, 1);
  await vi.waitFor(() =>
    expect(state()?.textContent).toContain("По этим фильтрам профилей нет"),
  );
  state()?.querySelector<HTMLButtonElement>("button")?.click();
  await vi.waitFor(() =>
    expect(document.querySelector(".profile-card")?.textContent).toContain(
      "Main",
    ),
  );
});

it("does not show first-run guidance when the presence lookup fails", async () => {
  await mount("/trades", 0, 0, true);
  await vi.waitFor(() =>
    expect(document.querySelector(".state-panel--error")).not.toBeNull(),
  );
  expect(state()).toBeNull();
});

it("does not render an empty journal for an invalid date interval", async () => {
  const { requests } = await mount(
    "/trades?period=custom&date_from=2026-02-01&date_to=2026-01-01",
  );
  await vi.waitFor(() =>
    expect(document.querySelector(".field-error")).not.toBeNull(),
  );
  expect(state()).toBeNull();
  expect(requests.some((url) => url.pathname === "/api/v1/trades")).toBe(false);
});

it("ignores presentation preferences and inactive date inputs", () => {
  expect(
    hasTradeFilters({
      page: 2,
      page_size: 50,
      sort: "quality_rating",
      order: "asc",
      review: "all",
      q: "  ",
    }),
  ).toBe(false);
  const conditions: TradeListParams[] = [
    { q: "BTC" },
    { trade_status: "open" },
    { review: "unreviewed" },
    { rated: false },
    { direction: "short" },
    { profile_id: 1 },
    { strategy_id: 1 },
    { date_from: "2026-01-01" },
    { date_to: "2026-02-01" },
  ];
  expect(conditions.every(hasTradeFilters)).toBe(true);
});

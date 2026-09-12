/** Draft creation stays in a drawer and opens the editable trade on success. */
import { afterEach, expect, it, vi } from "vitest";
import { createApp, h, type App } from "vue";
import { createPinia } from "pinia";
import { createMemoryHistory, createRouter, RouterView } from "vue-router";
import { QueryClient, VueQueryPlugin } from "@tanstack/vue-query";
import TradeCreateDialog from "@/features/trades/TradeCreateDialog.vue";
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

it("uses the active profile, retains input on errors and opens the draft", async () => {
  document.body.innerHTML = '<div class="tf-app"><div id="root"></div></div>';
  localStorage.clear();
  reloadTokens();
  i18n.global.locale.value = "en";
  HTMLElement.prototype.scrollIntoView = vi.fn();
  let fail = true;
  const posts: Record<string, unknown>[] = [];
  const instrument = {
    id: 3,
    exec_symbol: "BTCUSDT",
    product: "spot",
    is_active: true,
    is_archived: false,
  };
  vi.stubGlobal(
    "fetch",
    vi.fn(async (request: Request) => {
      const url = new URL(request.url);
      let items: unknown[] = [];
      if (request.method === "POST") {
        posts.push(await request.json());
        return new Response(
          JSON.stringify(
            fail ? { detail: { message: "Retry" } } : { id: 23, profile_id: 1 },
          ),
          {
            status: fail ? 503 : 201,
            headers: { "Content-Type": "application/json" },
          },
        );
      }
      if (url.pathname.endsWith("/profiles"))
        items = [1, 2].map((id) => ({
          id,
          name: "Profile " + id,
          venue_type: id === 1 ? "bybit" : "manual",
          is_archived: false,
        }));
      if (url.pathname.endsWith("/strategies"))
        items = [
          {
            id: 5,
            name: "Strategy",
            is_archived: false,
            allocations: [{ is_archived: false }],
          },
        ];
      if (url.pathname.endsWith("/instruments")) items = [instrument];
      const data = url.pathname.endsWith("/profiles/1")
        ? { id: 1, name: "Profile 1", venue_type: "bybit", is_archived: false }
        : url.pathname.endsWith("/instruments/3")
          ? instrument
          : { items, total: items.length, page: 1, page_size: 25 };
      return new Response(JSON.stringify(data), {
        headers: { "Content-Type": "application/json" },
      });
    }),
  );
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      {
        path: "/trades",
        component: {
          render: () =>
            h(TradeCreateDialog, { profileId: 1, returnTo: "/trades?q=BTC" }),
        },
      },
      {
        path: "/profiles/:profileId/trades/:tradeId",
        component: { template: "<p>Trade editor</p>" },
      },
    ],
  });
  query = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  await router.push("/trades?q=BTC");
  app = createApp({ render: () => h(RouterView) });
  app
    .use(createPinia())
    .use(i18n)
    .use(router)
    .use(VueQueryPlugin, { queryClient: query })
    .mount("#root");
  await vi.waitFor(() =>
    expect(document.querySelector(".tf-combobox-trigger")).not.toBeNull(),
  );
  expect(document.querySelector(".tf-form-dialog")).not.toBeNull();
  expect(document.body.textContent).not.toContain("Long");
  expect(document.body.textContent).not.toContain("Short");
  const submit = () =>
    document.querySelector<HTMLButtonElement>('button[type="submit"]')!;
  expect(submit().disabled).toBe(true);
  async function choose(index: number, label: string) {
    document
      .querySelectorAll<HTMLButtonElement>(".tf-combobox-trigger")
      [index]!.click();
    await vi.waitFor(() =>
      expect(
        [...document.querySelectorAll('[role="option"]')].some((item) =>
          item.textContent?.includes(label),
        ),
      ).toBe(true),
    );
    [...document.querySelectorAll<HTMLElement>('[role="option"]')]
      .find((item) => item.textContent?.includes(label))!
      .click();
  }
  expect(document.body.textContent).not.toContain("Select profile");
  await choose(0, "Strategy");
  await choose(1, "BTCUSDT");
  await vi.waitFor(() => expect(submit().disabled).toBe(false));
  submit().click();
  await vi.waitFor(() => expect(posts).toHaveLength(1));
  await vi.waitFor(() => expect(submit().disabled).toBe(false));
  expect(router.currentRoute.value.path).toBe("/trades");
  expect(posts[0]).toMatchObject({
    strategy_id: 5,
    instrument_id: 3,
    direction: "long",
  });
  expect(posts[0]).not.toHaveProperty("profile_id");
  fail = false;
  submit().click();
  await vi.waitFor(() =>
    expect(router.currentRoute.value.path).toBe("/profiles/1/trades/23"),
  );
  expect(router.currentRoute.value.query.returnTo).toBe("/trades?q=BTC");
});
